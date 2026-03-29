"""Draft composer agent — generates email reply drafts with proposed meeting times."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

if TYPE_CHECKING:
    from scheduler.calendar.client import CalendarClient
    from scheduler.classifier.intent import ClassificationResult
    from scheduler.gmail.client import GmailClient


logger = logging.getLogger(__name__)


def _analyze_draft_for_scheduling(
    draft_body: str,
    attendee_email: str,
    user_timezone: str,
) -> dict:
    """Single LLM call to analyze a composed draft and extract scheduling info.

    Returns a dict with:
      - mode: "suggested" or "availability"
      - suggested_windows: list of {date, start, end} if mode is "suggested"
      - duration_minutes: int
      - event_summary: str
    """
    from anthropic import Anthropic
    from scheduler.config import config

    if not config.anthropic_api_key:
        return {"mode": "availability"}

    client = Anthropic(api_key=config.anthropic_api_key)

    from datetime import date as date_type
    today = date_type.today().isoformat()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You analyze email drafts to extract scheduling information.\n\n"
            f"Today's date is {today}.\n\n"
            "Given a draft email body, determine:\n"
            "1. Does this draft CONFIRM a single specific time that was already agreed upon, "
            "or is it accepting a proposed time? If yes, mode is \"confirmation\" — "
            "the meeting time is settled and no scheduling link is needed.\n"
            "2. Does this draft propose MULTIPLE meeting time options for the recipient to "
            "choose from? If yes, mode is \"suggested\".\n"
            "3. Otherwise (general reply, no times proposed), mode is \"availability\".\n\n"
            "If \"suggested\": extract the EXACT proposed time slots from the email. "
            "Each slot should match what the email actually proposes — do NOT create broad "
            "ranges or expand them. For example, if the email says '10:00 AM - 10:30 AM on "
            "Monday', the window should be exactly {\"date\": \"2026-03-30\", \"start\": \"10:00\", "
            "\"end\": \"10:30\"}. If the email says '2pm on Tuesday' without an end time, use "
            "the estimated meeting duration to set the end time.\n\n"
            f"All times are in the user's timezone: {user_timezone}.\n"
            "Make sure dates use the correct year based on today's date.\n\n"
            "For duration_minutes: look at the proposed time ranges (e.g. 10:00-10:30 = 30 min, "
            "2:00-3:00 = 60 min). If the email mentions a duration like '1 hour' or '30 minutes', "
            "use that. Default to 30 if unclear.\n\n"
            "Extract a short event summary from the email context.\n\n"
            "Respond with ONLY a JSON object:\n"
            "{\n"
            '  "mode": "confirmation" | "suggested" | "availability",\n'
            '  "suggested_windows": [{"date": "YYYY-MM-DD", "start": "HH:MM", "end": "HH:MM"}],\n'
            '  "duration_minutes": integer,\n'
            '  "event_summary": "short summary"\n'
            "}\n"
            "suggested_windows should be empty [] if mode is \"confirmation\" or \"availability\"."
        ),
        messages=[{"role": "user", "content": f"Draft email body:\n\n{draft_body}"}],
    )

    try:
        text = response.content[0].text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        return {
            "mode": result.get("mode", "availability"),
            "suggested_windows": result.get("suggested_windows", []),
            "duration_minutes": result.get("duration_minutes", 30),
            "event_summary": result.get("event_summary", "Meeting"),
        }
    except (json.JSONDecodeError, IndexError, KeyError):
        logger.debug("Failed to parse scheduling analysis response", exc_info=True)
        return {"mode": "availability"}


def _create_scheduling_link_for_draft(
    user_id: str,
    draft_body: str,
    attendee_email: str,
    thread_id: str | None,
    subject: str,
    user_timezone: str,
) -> str | None:
    """Analyze a draft and create the appropriate scheduling link. Returns the link URL or None."""
    try:
        analysis = _analyze_draft_for_scheduling(draft_body, attendee_email, user_timezone)
    except Exception:
        logger.debug("Failed to analyze draft for scheduling link", exc_info=True)
        return None
    return _create_scheduling_link_from_analysis(
        user_id=user_id,
        analysis=analysis,
        attendee_email=attendee_email,
        thread_id=thread_id,
        subject=subject,
        user_timezone=user_timezone,
    )


def _create_scheduling_link_from_analysis(
    user_id: str,
    analysis: dict,
    attendee_email: str,
    thread_id: str | None,
    subject: str,
    user_timezone: str,
) -> str | None:
    """Create a scheduling link from a pre-computed analysis. Returns the link URL or None."""
    from scheduler.db import get_user_by_id

    user = get_user_by_id(user_id)
    if not user or not user.scheduled_branding_enabled:
        return None

    from scheduler.config import config
    from scheduler.db import create_scheduling_link as db_create

    try:
        mode = analysis.get("mode", "availability")

        # Confirmation emails (single agreed time) just get "Sent by Scheduled"
        if mode == "confirmation":
            return None

        link = db_create(
            user_id=user_id,
            mode=mode,
            attendee_email=attendee_email,
            event_summary=analysis.get("event_summary", subject or "Meeting"),
            duration_minutes=analysis.get("duration_minutes", 30),
            tz=user_timezone,
            suggested_windows=analysis.get("suggested_windows", []),
            thread_id=thread_id,
        )
        return f"{config.web_app_url}/schedule/{link.id}"
    except Exception:
        logger.debug("Failed to create scheduling link for draft", exc_info=True)
        return None


def _build_footer(user_id: str, scheduling_link_url: str | None = None) -> tuple[str, bool]:
    """Build the email footer HTML. Returns (footer_html, should_use_html).

    Returns empty string if branding is disabled.
    """
    from scheduler.db import get_user_by_id

    user = get_user_by_id(user_id)
    if not user or not user.scheduled_branding_enabled:
        return "", False

    display_name = user.display_name or user.email.split("@")[0]
    capitalized_name = display_name.title()

    if not scheduling_link_url:
        return (
            '<br><br>sent by <a href="https://tryscheduled.com">Scheduled.</a>',
            True,
        )

    return (
        f'<br><br>Use <a href="{scheduling_link_url}">Scheduled</a> to find a time '
        f'automatically with {html.escape(capitalized_name)}',
        True,
    )


def _apply_footer(body: str, user_id: str, scheduling_link_url: str | None = None) -> tuple[str, str]:
    """Apply the branded footer to a plain-text email body.

    Returns (final_body, content_type).
    """
    footer, should_html = _build_footer(user_id, scheduling_link_url)
    if not footer:
        return body, "plain"
    html_body = html.escape(body).replace("\n", "<br>")
    html_body += footer
    return html_body, "html"


class DraftBackend(Protocol):
    def load_guide(self, name: str) -> str | None: ...

    def get_calendar_events(self, start_date: str, end_date: str) -> list[dict]: ...

    def get_user_timezone(self) -> str: ...

    def read_thread(self, thread_id: str) -> list[dict]: ...

    def create_draft(self, args: dict, scheduling_link_url: str | None = None) -> dict: ...

    def send_email(self, args: dict, scheduling_link_url: str | None = None) -> dict: ...


class LocalDraftBackend:
    """Draft backend that talks directly to Gmail/Calendar and local DB state."""

    def __init__(self, gmail_client: GmailClient, calendar_client: CalendarClient, user_id: str, thread_messages: list[dict] | None = None, refresh_count: int = 0):
        self._gmail = gmail_client
        self._calendar = calendar_client
        self._user_id = user_id
        self._thread_messages = thread_messages or []
        self._refresh_count = refresh_count

    def load_guide(self, name: str) -> str | None:
        from scheduler.guides import load_guide

        return load_guide(name, user_id=self._user_id)

    def get_user_timezone(self) -> str:
        return self._calendar.get_user_timezone()

    def get_calendar_events(self, start_date: str, end_date: str) -> list[dict]:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        events = self._calendar.get_all_events(start, end, include_primary=True)
        return [
            {
                "id": e.id,
                "summary": e.summary,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "description": e.description,
                "source": e.source,
            }
            for e in events
        ]

    def read_thread(self, thread_id: str) -> list[dict]:
        thread = self._gmail.get_thread(thread_id)
        return [
            {
                "id": m.id,
                "thread_id": m.thread_id,
                "sender": m.sender,
                "recipient": m.recipient,
                "cc": m.cc,
                "subject": m.subject,
                "body": m.body,
                "date": m.date.isoformat(),
                "snippet": m.snippet,
            }
            for m in thread
        ]

    def create_draft(self, args: dict, scheduling_link_url: str | None = None) -> dict:
        body = args["body"]
        user_tz = self._calendar.get_user_timezone()

        # Analyze draft once — used for both scheduling link and staleness tracking
        suggested_windows: list[dict] = []
        try:
            analysis = _analyze_draft_for_scheduling(
                body, args.get("to", ""), user_tz,
            )
            suggested_windows = analysis.get("suggested_windows", [])
        except Exception:
            analysis = None

        if not scheduling_link_url and analysis:
            scheduling_link_url = _create_scheduling_link_from_analysis(
                user_id=self._user_id,
                analysis=analysis,
                attendee_email=args.get("to", ""),
                thread_id=args.get("thread_id"),
                subject=args.get("subject", "Meeting"),
                user_timezone=user_tz,
            )

        body, content_type = _apply_footer(body, self._user_id, scheduling_link_url)

        draft_id = self._gmail.create_draft(
            thread_id=args["thread_id"],
            to=args["to"],
            subject=args["subject"],
            body=body,
            content_type=content_type,
            cc=args.get("cc", ""),
        )

        from scheduler import analytics
        analytics.record_draft_composed(
            user_id=self._user_id,
            thread_id=args["thread_id"],
            draft_id=draft_id,
            thread_messages=self._thread_messages,
            subject=args["subject"],
            body=body,
            refresh_count=self._refresh_count,
            suggested_windows=suggested_windows,
        )

        return {"draft_id": draft_id}

    def send_email(self, args: dict, scheduling_link_url: str | None = None) -> dict:
        body = args["body"]

        if not scheduling_link_url:
            user_tz = self._calendar.get_user_timezone()
            scheduling_link_url = _create_scheduling_link_for_draft(
                user_id=self._user_id,
                draft_body=body,
                attendee_email=args.get("to", ""),
                thread_id=args.get("thread_id"),
                subject=args.get("subject", "Meeting"),
                user_timezone=user_tz,
            )

        body, content_type = _apply_footer(body, self._user_id, scheduling_link_url)

        message_id = self._gmail.send_email(
            thread_id=args["thread_id"],
            to=args["to"],
            subject=args["subject"],
            body=body,
            content_type=content_type,
            cc=args.get("cc", ""),
        )

        from scheduler import analytics
        analytics.record_draft_composed(
            user_id=self._user_id,
            thread_id=args["thread_id"],
            draft_id=f"sent:{message_id}",
            thread_messages=self._thread_messages,
            subject=args["subject"],
            body=body,
            was_autopilot=True,
        )

        return {"message_id": message_id, "status": "sent"}


def _email_field(email: Any, key: str) -> Any:
    if isinstance(email, dict):
        return email.get(key)
    return getattr(email, key)


def _classification_dict(classification: "ClassificationResult" | dict) -> dict:
    if isinstance(classification, dict):
        return {
            "intent": classification.get("intent", "doesnt_need_draft"),
            "confidence": classification.get("confidence", 0.0),
            "summary": classification.get("summary", ""),
            "proposed_times": list(classification.get("proposed_times") or []),
            "participants": list(classification.get("participants") or []),
            "duration_minutes": classification.get("duration_minutes"),
        }

    return {
        "intent": classification.intent.value,
        "confidence": classification.confidence,
        "summary": classification.summary,
        "proposed_times": classification.proposed_times,
        "participants": classification.participants,
        "duration_minutes": classification.duration_minutes,
    }


class DraftComposer:
    """Agent that composes and creates draft replies for scheduling emails."""

    def __init__(self, backend: DraftBackend, user_id: str, *, autopilot: bool = False, user_email: str | None = None):
        self._backend = backend
        self._user_id = user_id
        self._autopilot = autopilot
        self._user_email = user_email

    def _build_system_prompt(self) -> str:
        parts = [
            "You are a draft composer agent for a scheduling assistant. "
            "Your job is to read the email thread, check the user's calendar "
            "for availability, and compose a natural-sounding draft reply."
        ]

        from scheduler.guides.defaults import DEFAULT_EMAIL_STYLE, DEFAULT_SCHEDULING_PREFERENCES

        scheduling_prefs = self._backend.load_guide("scheduling_preferences")
        parts.append(
            "\n\n## Scheduling Preferences\n"
            "Use these observed patterns when proposing times:\n\n"
            + (scheduling_prefs or DEFAULT_SCHEDULING_PREFERENCES)
        )

        email_style = self._backend.load_guide("email_style")
        parts.append(
            "\n\n## Email Style Guide\n"
            "Match this writing style in the draft:\n\n"
            + (email_style or DEFAULT_EMAIL_STYLE)
        )

        if self._user_email:
            parts.append(
                "\n\n## User Identity\n"
                f"You are composing on behalf of: {self._user_email}\n"
                "This is the user's email address. In group threads, use this to identify "
                "which messages are from the user vs. other participants. Sign off as the user, "
                "not as any other participant."
            )

        parts.append(
            "\n\n## Tone & Etiquette\n"
            "- Never re-suggest times that were already declined or said to not work in the thread.\n"
            "- Be warm, friendly, and accommodating — never passive-aggressive.\n"
            "- Don't express frustration about scheduling difficulty.\n"
            "- Be understanding when people can't make certain times.\n"
            "- Avoid phrases like \"as I mentioned\", \"per my last email\", \"let's try this again\", "
            "or anything that could sound impatient or annoyed."
        )

        return "\n".join(parts)

    def _build_tools(self) -> tuple[list, dict, dict]:
        draft_result: dict = {"draft_id": None}
        invite_proposal: dict = {"proposal": None}

        backend = self._backend

        @tool(
            "get_calendar_events",
            "Get all events from the user's calendars (primary + scheduled) in a date range. "
            "Use this to see what the user already has scheduled and figure out when they're free.",
            {"start_date": str, "end_date": str},
        )
        async def get_calendar_events(args):
            payload = backend.get_calendar_events(args["start_date"], args["end_date"])
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "read_thread",
            "Read the full email thread for context on what's being scheduled.",
            {"thread_id": str},
        )
        async def read_thread(args):
            payload = backend.read_thread(args["thread_id"])
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "create_draft",
            "Create a draft reply in Gmail with the composed response.",
            {
                "thread_id": str,
                "to": str,
                "cc": str,
                "subject": str,
                "body": str,
            },
        )
        async def create_draft(args):
            result = backend.create_draft(args)
            draft_result["draft_id"] = result.get("draft_id")
            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        @tool(
            "add_calendar_event",
            "Add an event to the user's scheduled calendar (e.g. when a time is confirmed but no invite exists). "
            "IMPORTANT: start and end must include the timezone offset (e.g. '2026-04-01T14:00:00-07:00'), "
            "not bare UTC times.",
            {"summary": str, "start": str, "end": str, "description": str},
        )
        async def add_calendar_event(args):
            result = backend.add_calendar_event(args)
            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        @tool(
            "propose_invite",
            "Propose a calendar invite to be sent when the user sends this draft. "
            "ONLY use this when the draft is a final confirmation of a time that the other "
            "party already agreed to. Do NOT use this when merely proposing times — the other "
            "party may not be able to accept. The invite will only be created after the user "
            "sends the draft and an agent verifies the sent message still confirms the meeting. "
            "Use add_calendar_event for personal reminders/holds.",
            {
                "attendee_emails": list[str],
                "event_summary": str,
                "event_start": str,
                "event_end": str,
                "add_google_meet": bool,
                "location": str,
            },
        )
        async def propose_invite(args):
            invite_proposal["proposal"] = args
            return {"content": [{"type": "text", "text": json.dumps({"status": "invite_proposed", **args})}]}

        @tool(
            "get_booking_page_times",
            "Get available time slots from an external booking page (Calendly, Cal.com). "
            "Use this when someone shares a booking link and you need to see what times "
            "are available before choosing one. Returns a list of times like ['9:00am', '10:30am'].",
            {"url": str, "date": str},
        )
        async def get_booking_page_times(args):
            from datetime import date as date_type

            from scheduler.booking import get_available_times

            target = date_type.fromisoformat(args["date"])
            result = await get_available_times(args["url"], target)
            payload = {"times": result.times, "date": str(result.date)}
            if result.error_detail:
                payload["error"] = result.error_detail
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "book_meeting_slot",
            "Book a specific time slot on an external booking page (Calendly, Cal.com). "
            "Use get_booking_page_times first to see available slots, then use this to "
            "book one. Only use after checking the user's own calendar for conflicts.",
            {"url": str, "date": str, "time": str, "name": str, "email": str, "title": str},
        )
        async def book_meeting_slot(args):
            from datetime import date as date_type

            from scheduler.booking import book_slot

            target = date_type.fromisoformat(args["date"])
            result = await book_slot(
                args["url"], target, args["time"],
                args["name"], args["email"], title=args.get("title", ""),
            )
            payload = {"status": result.status.value}
            if result.confirmation_message:
                payload["confirmation"] = result.confirmation_message
            if result.error_detail:
                payload["error"] = result.error_detail
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        all_tools = [
            get_calendar_events, read_thread, create_draft, add_calendar_event,
            propose_invite, get_booking_page_times, book_meeting_slot,
        ]

        if self._autopilot:

            @tool(
                "send_email",
                "Send an email reply directly (not a draft). Use this instead of create_draft "
                "when you are confident the reply is ready to send. Do NOT use this for group "
                "meetings — use create_draft instead so the user can review before sending.",
                {"thread_id": str, "to": str, "cc": str, "subject": str, "body": str},
            )
            async def send_email(args):
                result = backend.send_email(args)
                draft_result["draft_id"] = f"sent:{result['message_id']}"
                return {"content": [{"type": "text", "text": json.dumps(result)}]}

            all_tools.append(send_email)

        return all_tools, draft_result, invite_proposal

    def compose_and_create_draft(self, email: Any, classification: "ClassificationResult" | dict, current_datetime: str | None = None) -> dict:
        system_prompt = self._build_system_prompt()
        tools, draft_result, invite_proposal = self._build_tools()
        server = create_sdk_mcp_server("draft-tools", tools=tools)
        classification_dict = _classification_dict(classification)

        user_timezone = self._backend.get_user_timezone()

        datetime_line = f"The current date and time is {current_datetime}.\n\n" if current_datetime else ""

        prompt = (
            "You are a scheduling draft composer.\n\n"
            + datetime_line
            + f"The user's timezone is {user_timezone}. All times you propose MUST be in the "
            "user's local timezone with the offset included. "
            "For example, if the user is in America/Los_Angeles, 2pm is '2026-03-20T14:00:00-07:00', "
            "NOT '2026-03-20T21:00:00' (that would be 9pm local).\n\n"
            "You are given an incoming email and a structured classification of that email. "
            "Your job is to:\n"
            "1. Read the full email thread using read_thread. Pay attention to any times that "
            "were proposed and declined.\n"
            "2. Check if the thread is already resolved before proceeding:\n"
            "   - If a time was already confirmed and a calendar invite exists, do NOT create a draft — just stop.\n"
            "   - If someone else already replied on the user's behalf, do NOT create a draft — just stop.\n"
            "   - If a time was confirmed but no calendar invite was sent, draft a confirmation reply.\n"
            "   - If a meeting was cancelled/rescheduled but the calendar still has the old event, note this discrepancy.\n"
            "3. Inspect the user's availability using get_calendar_events over a reasonable window "
            "(for example, the next 14 days).\n"
            "4. Based on the thread context, draft the appropriate response:\n"
            "   - If someone is requesting a meeting or proposing times: propose concrete meeting times "
            "that respect the user's existing commitments. "
            "NEVER re-suggest a time that someone already said doesn't work.\n"
            "   - If someone is cancelling or rescheduling: acknowledge it. "
            "If rescheduling, suggest alternative times based on the user's availability. "
            "Note if the user's calendar still has the old event that should be removed.\n"
            "   - If someone is confirming a time: draft a brief confirmation. Verify there is no "
            "calendar conflict at the confirmed time.\n"
            "5. Only call propose_invite when your reply is a FINAL CONFIRMATION of a meeting time "
            "that the other party already agreed to. Do NOT call propose_invite when you are merely "
            "proposing or suggesting times — the other party hasn't accepted yet, so sending an invite "
            "would be premature. The invite will NOT be sent immediately — it will only be created after "
            "the user sends the draft and an agent verifies the sent message. "
            "Use add_calendar_event for personal calendar holds.\n"
            "6. If the email contains a booking link (Calendly, Cal.com), use get_booking_page_times "
            "to see what slots are available on that page, then cross-reference with the user's "
            "calendar. If a good slot exists, use book_meeting_slot to book it, then draft a "
            "confirmation reply. If no slot works, draft a reply explaining the conflict.\n"
            "7. Consider location preferences when drafting replies. If the thread mentions an in-person "
            "meeting but no location, suggest one based on any observed location preferences. "
            "If a location is mentioned in the thread, acknowledge it in the reply.\n"
            "8. Create a natural-sounding reply. Do not use passive-aggressive phrases like "
            "\"as I mentioned\", \"per my last email\", or \"let's try this again\". "
            "Be warm and accommodating, not impatient. "
            + (
                "AUTOPILOT MODE IS ON: You should send the email directly using send_email instead of "
                "creating a draft. The ONLY exception is group meetings (3+ participants including the user) — "
                "for group meetings, use create_draft instead because the user may need to coordinate with "
                "multiple people before committing. For 1-on-1 meetings, always use send_email.\n\n"
                "IMPORTANT: If the thread is already fully resolved (step 2), do NOT create a draft or send an email. "
                "Simply stop.\n\n"
                if self._autopilot
                else
                "Create a natural-sounding draft reply using create_draft. "
                "When you are satisfied with the draft, call create_draft exactly once.\n\n"
                "IMPORTANT: If the thread is already fully resolved (step 2), do NOT call create_draft. "
                "Simply stop without creating a draft.\n\n"
            )
            + (f"You are composing on behalf of: {self._user_email}\n\n" if self._user_email else "")
            + "When replying, preserve CC recipients from the thread. Include anyone who was CC'd "
            "on the previous messages in your reply's cc field, but exclude the user's own email "
            "address from CC.\n\n"
            + "Email summary (for quick reference):\n"
            f"Message ID: {_email_field(email, 'id')}\n"
            f"Thread ID: {_email_field(email, 'thread_id')}\n"
            f"Sender: {_email_field(email, 'sender')}\n"
            f"Recipient: {_email_field(email, 'recipient')}\n"
            f"CC: {_email_field(email, 'cc')}\n"
            f"Subject: {_email_field(email, 'subject')}\n"
            f"Snippet: {_email_field(email, 'snippet')}\n\n"
            "Classification JSON:\n"
            f"{json.dumps(classification_dict, indent=2)}\n"
        )

        options = ClaudeAgentOptions(
            mcp_servers={"draft": server},
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",
            model="claude-opus-4-6",
        )

        os.environ.pop("CLAUDECODE", None)

        async def _run_agent():
            client = ClaudeSDKClient(options=options)
            await client.connect()
            try:
                await client.query(prompt)
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                logger.info("draft_composer: %s", block.text)
                    elif isinstance(message, ResultMessage):
                        logger.info("draft_composer result: %s", message.result)
                    else:
                        logger.info("draft_composer message: %s", type(message).__name__)
            finally:
                await client.disconnect()

        asyncio.run(_run_agent())
        return {
            "draft_id": draft_result.get("draft_id") or None,
            "invite_proposal": invite_proposal.get("proposal"),
        }
