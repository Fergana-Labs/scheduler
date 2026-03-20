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


class DraftBackend(Protocol):
    def load_guide(self, name: str) -> str | None: ...

    def get_calendar_events(self, start_date: str, end_date: str) -> list[dict]: ...

    def get_user_timezone(self) -> str: ...

    def read_thread(self, thread_id: str) -> list[dict]: ...

    def create_draft(self, args: dict) -> dict: ...

    def send_email(self, args: dict) -> dict: ...

    def add_calendar_event(self, args: dict) -> dict: ...


class LocalDraftBackend:
    """Draft backend that talks directly to Gmail/Calendar and local DB state."""

    def __init__(self, gmail_client: GmailClient, calendar_client: CalendarClient, user_id: str):
        self._gmail = gmail_client
        self._calendar = calendar_client
        self._user_id = user_id

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
                "subject": m.subject,
                "body": m.body,
                "date": m.date.isoformat(),
                "snippet": m.snippet,
            }
            for m in thread
        ]

    def create_draft(self, args: dict) -> dict:
        body = args["body"]
        content_type = "plain"

        from scheduler.db import create_pending_invite, get_user_by_id

        user = get_user_by_id(self._user_id)
        if user and user.stash_branding_enabled:
            html_body = html.escape(body).replace("\n", "<br>")
            html_body += '<br><br>sent by <a href="https://tryscheduled.com">Scheduled.</a>'
            body = html_body
            content_type = "html"

        draft_id = self._gmail.create_draft(
            thread_id=args["thread_id"],
            to=args["to"],
            subject=args["subject"],
            body=body,
            content_type=content_type,
        )

        if args.get("send_invite"):
            create_pending_invite(
                user_id=self._user_id,
                thread_id=args["thread_id"],
                attendee_email=args["invite_attendee_email"],
                event_summary=args["invite_event_summary"],
                event_start=datetime.fromisoformat(args["invite_event_start"]),
                event_end=datetime.fromisoformat(args["invite_event_end"]),
                add_google_meet=args.get("invite_add_google_meet", False),
            )

        return {"draft_id": draft_id}

    def send_email(self, args: dict) -> dict:
        body = args["body"]
        content_type = "plain"

        from scheduler.db import get_user_by_id

        user = get_user_by_id(self._user_id)
        if user and user.stash_branding_enabled:
            html_body = html.escape(body).replace("\n", "<br>")
            html_body += '<br><br>sent by <a href="https://tryscheduled.com">Scheduled.</a>'
            body = html_body
            content_type = "html"

        message_id = self._gmail.send_email(
            thread_id=args["thread_id"],
            to=args["to"],
            subject=args["subject"],
            body=body,
            content_type=content_type,
        )
        return {"message_id": message_id, "status": "sent"}

    def add_calendar_event(self, args: dict) -> dict:
        from scheduler.calendar.client import Event

        event = Event(
            id=None,
            summary=args["summary"],
            start=datetime.fromisoformat(args["start"]),
            end=datetime.fromisoformat(args["end"]),
            description=args.get("description", ""),
            source="gmail",
        )
        return {"event_id": self._calendar.add_event(event)}


def _email_field(email: Any, key: str) -> Any:
    if isinstance(email, dict):
        return email.get(key)
    return getattr(email, key)


def _classification_dict(classification: "ClassificationResult" | dict) -> dict:
    if isinstance(classification, dict):
        return {
            "intent": classification.get("intent", "not_scheduling"),
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

    def __init__(self, backend: DraftBackend, user_id: str, *, autopilot: bool = False):
        self._backend = backend
        self._user_id = user_id
        self._autopilot = autopilot

    def _build_system_prompt(self) -> str:
        parts = [
            "You are a draft composer agent for a scheduling assistant. "
            "Your job is to read the email thread, check the user's calendar "
            "for availability, and compose a natural-sounding draft reply."
        ]

        scheduling_prefs = self._backend.load_guide("scheduling_preferences")
        if scheduling_prefs:
            parts.append(
                "\n\n## Scheduling Preferences\n"
                "Use these observed patterns when proposing times:\n\n"
                + scheduling_prefs
            )

        email_style = self._backend.load_guide("email_style")
        if email_style:
            parts.append(
                "\n\n## Email Style Guide\n"
                "Match this writing style in the draft:\n\n"
                + email_style
            )

        return "\n".join(parts)

    def _build_tools(self) -> tuple[list, dict]:
        draft_result: dict = {"draft_id": None}

        @tool(
            "get_calendar_events",
            "Get all events from the user's calendars (primary + stash) in a date range. "
            "Use this to see what the user already has scheduled and figure out when they're free.",
            {"start_date": str, "end_date": str},
        )
        async def get_calendar_events(args):
            payload = self._backend.get_calendar_events(args["start_date"], args["end_date"])
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "read_thread",
            "Read the full email thread for context on what's being scheduled.",
            {"thread_id": str},
        )
        async def read_thread(args):
            payload = self._backend.read_thread(args["thread_id"])
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "create_draft",
            "Create a draft reply in Gmail with the composed response. "
            "Set send_invite=true to automatically create a calendar invite when the user sends this draft. "
            "When send_invite is true, you must also provide invite_attendee_email, invite_event_summary, "
            "invite_event_start, and invite_event_end. Set invite_add_google_meet=true to attach a Google Meet link.",
            {
                "thread_id": str,
                "to": str,
                "subject": str,
                "body": str,
                "send_invite": bool,
                "invite_attendee_email": str,
                "invite_event_summary": str,
                "invite_event_start": str,
                "invite_event_end": str,
                "invite_add_google_meet": bool,
            },
        )
        async def create_draft(args):
            result = self._backend.create_draft(args)
            draft_result["draft_id"] = result.get("draft_id")
            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        @tool(
            "add_calendar_event",
            "Add an event to the user's stash calendar (e.g. when a time is confirmed but no invite exists).",
            {"summary": str, "start": str, "end": str, "description": str},
        )
        async def add_calendar_event(args):
            result = self._backend.add_calendar_event(args)
            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        all_tools = [get_calendar_events, read_thread, create_draft, add_calendar_event]

        if self._autopilot:

            @tool(
                "send_email",
                "Send an email reply directly (not a draft). Use this instead of create_draft "
                "when you are confident the reply is ready to send. Do NOT use this for group "
                "meetings — use create_draft instead so the user can review before sending.",
                {"thread_id": str, "to": str, "subject": str, "body": str},
            )
            async def send_email(args):
                result = self._backend.send_email(args)
                draft_result["draft_id"] = f"sent:{result['message_id']}"
                return {"content": [{"type": "text", "text": json.dumps(result)}]}

            all_tools.append(send_email)

        return all_tools, draft_result

    def compose_and_create_draft(self, email: Any, classification: "ClassificationResult" | dict) -> str | None:
        system_prompt = self._build_system_prompt()
        tools, draft_result = self._build_tools()
        server = create_sdk_mcp_server("draft-tools", tools=tools)
        classification_dict = _classification_dict(classification)

        user_timezone = self._backend.get_user_timezone()

        prompt = (
            "You are a scheduling draft composer.\n\n"
            f"The user's timezone is {user_timezone}. All times you propose and all "
            "invite_event_start/invite_event_end values MUST include this timezone offset. "
            "For example, if the user is in America/New_York, use '2026-03-20T15:00:00-04:00' "
            "not '2026-03-20T15:00:00'.\n\n"
            "You are given an incoming email and a structured classification of that email. "
            "Your job is to:\n"
            "1. Read the full email thread using read_thread.\n"
            "2. Check if the thread is already resolved before proceeding:\n"
            "   - If a time was already confirmed and a calendar invite exists, do NOT create a draft — just stop.\n"
            "   - If someone else already replied on the user's behalf, do NOT create a draft — just stop.\n"
            "   - If a time was confirmed but no calendar invite was sent, create the event using "
            "add_calendar_event and draft a confirmation reply.\n"
            "   - If a meeting was cancelled/rescheduled but the calendar still has the old event, note this discrepancy.\n"
            "3. Inspect the user's availability using get_calendar_events over a reasonable window "
            "(for example, the next 14 days).\n"
            "4. Based on the intent:\n"
            "   - If requesting_meeting or proposing_times: propose concrete meeting times that respect "
            "the user's existing commitments and the extracted details from the classification.\n"
            "   - If cancelling_rescheduling: acknowledge the cancellation or reschedule request. "
            "If rescheduling, suggest alternative times based on the user's availability. "
            "Note if the user's calendar still has the old event that should be removed.\n"
            "   - If confirming_time: draft a brief confirmation. Verify there is no calendar conflict "
            "at the confirmed time.\n"
            "5. Consider location preferences when drafting replies. If the thread mentions an in-person "
            "meeting but no location, suggest one based on any observed location preferences. "
            "If a location is mentioned in the thread, acknowledge it in the reply.\n"
            "6. Create a natural-sounding reply. "
            + (
                "AUTOPILOT MODE IS ON: You should send the email directly using send_email instead of "
                "creating a draft. The ONLY exception is group meetings (3+ participants including the user) — "
                "for group meetings, use create_draft instead because the user may need to coordinate with "
                "multiple people before committing. For 1-on-1 meetings, always use send_email.\n\n"
                "When your reply proposes a specific meeting time, set send_invite=true on create_draft and "
                "fill in the invite fields (invite_attendee_email, invite_event_summary, "
                "invite_event_start, invite_event_end). This will automatically send a calendar invite when "
                "the user sends the draft. When you set send_invite=true, mention in the email body that you're "
                "sending a calendar invite (e.g. 'I've sent over a calendar invite as well.'). "
                "If the meeting is virtual or no physical location is specified, set invite_add_google_meet=true "
                "to attach a Google Meet link to the invite and mention the Meet link in your reply.\n\n"
                "IMPORTANT: If the thread is already fully resolved (step 2), do NOT create a draft or send an email. "
                "Simply stop.\n\n"
                if self._autopilot
                else
                "Create a natural-sounding draft reply using create_draft. "
                "When you are satisfied with the draft, call create_draft exactly once.\n"
                "If your draft proposes a specific meeting time, set send_invite=true on create_draft "
                "and fill in the invite fields (invite_attendee_email, invite_event_summary, "
                "invite_event_start, invite_event_end). This will automatically send a calendar invite "
                "when the user sends the draft. Only do this when a concrete time is being proposed. "
                "When you set send_invite=true, mention in the email body that you're sending a calendar invite "
                "(e.g. 'I've sent over a calendar invite as well.'). "
                "If the meeting is virtual or no physical location is specified, set invite_add_google_meet=true "
                "to attach a Google Meet link to the invite and mention the Meet link in your reply.\n\n"
                "IMPORTANT: If the thread is already fully resolved (step 2), do NOT call create_draft. "
                "Simply stop without creating a draft.\n\n"
            )
            + "Email summary (for quick reference):\n"
            f"Message ID: {_email_field(email, 'id')}\n"
            f"Thread ID: {_email_field(email, 'thread_id')}\n"
            f"Sender: {_email_field(email, 'sender')}\n"
            f"Recipient: {_email_field(email, 'recipient')}\n"
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
        return draft_result.get("draft_id") or None
