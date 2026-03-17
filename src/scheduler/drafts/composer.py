"""Draft composer agent — generates email reply drafts with proposed meeting times.

This is an AGENT (not a simple LLM completion). It uses the Claude Agent SDK
with tools to:
- Read the email thread for full context
- Read the user's calendar events directly to determine availability
- Compose a natural-sounding draft reply with proposed times
- Create the draft in Gmail

An agent is used here (rather than a single completion) because the drafting
process benefits from the agent reading through evidence, checking multiple
date ranges, and iterating on the reply quality.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

from scheduler.calendar.client import CalendarClient
from scheduler.classifier.intent import ClassificationResult
from scheduler.config import config
from scheduler.gmail.client import Email, GmailClient
from scheduler.guides import load_guide

if TYPE_CHECKING:
    from claude_agent_sdk import MCPServer


# Tools the draft composer agent has access to
DRAFT_AGENT_TOOLS = [
    {
        "name": "get_calendar_events",
        "description": "Get all events from the user's calendars (primary + stash) in a date range. Use this to see what the user already has scheduled and figure out when they're free.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date (ISO format)"},
                "end_date": {"type": "string", "description": "End date (ISO format)"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "read_thread",
        "description": "Read the full email thread for context on what's being scheduled.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string", "description": "Gmail thread ID"},
            },
            "required": ["thread_id"],
        },
    },
    {
        "name": "create_draft",
        "description": "Create a draft reply in Gmail with the composed response. Set send_invite=true to automatically create a calendar invite when the user sends this draft.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string", "description": "Thread to reply to"},
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body text"},
                "send_invite": {"type": "boolean", "description": "If true, automatically create a calendar invite when the user sends this draft", "default": False},
                "invite_attendee_email": {"type": "string", "description": "Attendee email for the invite (required if send_invite is true)"},
                "invite_event_summary": {"type": "string", "description": "Event title (required if send_invite is true)"},
                "invite_event_start": {"type": "string", "description": "Event start time ISO format (required if send_invite is true)"},
                "invite_event_end": {"type": "string", "description": "Event end time ISO format (required if send_invite is true)"},
                "invite_add_google_meet": {"type": "boolean", "description": "If true, attach a Google Meet link to the calendar invite. Only relevant when send_invite is true.", "default": False},
            },
            "required": ["thread_id", "to", "subject", "body"],
        },
    },
]


class DraftComposer:
    """Agent that composes and creates draft replies for scheduling emails.

    Uses an agentic loop so it can read threads, check the calendar directly,
    reason about the user's real availability, and iterate on the draft
    before creating it.
    """

    def __init__(self, gmail_client: GmailClient, calendar_client: CalendarClient, user_id: str, *, autopilot: bool = False):
        self._gmail = gmail_client
        self._calendar = calendar_client
        self._user_id = user_id
        self._autopilot = autopilot

    def _build_system_prompt(self) -> str:
        """Build the system prompt, injecting guide files if they exist."""
        parts = [
            "You are a draft composer agent for a scheduling assistant. "
            "Your job is to read the email thread, check the user's calendar "
            "for availability, and compose a natural-sounding draft reply."
        ]

        scheduling_prefs = load_guide("scheduling_preferences", user_id=self._user_id)
        if scheduling_prefs:
            parts.append(
                "\n\n## Scheduling Preferences\n"
                "Use these observed patterns when proposing times:\n\n"
                + scheduling_prefs
            )

        email_style = load_guide("email_style", user_id=self._user_id)
        if email_style:
            parts.append(
                "\n\n## Email Style Guide\n"
                "Match this writing style in the draft:\n\n"
                + email_style
            )

        return "\n".join(parts)

    def _build_tools(self) -> tuple[list, dict]:
        """Build Agent SDK tools for the draft composer agent."""

        draft_result: dict = {"draft_id": None}

        @tool(
            "get_calendar_events",
            "Get all events from the user's calendars (primary + stash) in a date range. "
            "Use this to see what the user already has scheduled and figure out when they're free.",
            {"start_date": str, "end_date": str},
        )
        async def get_calendar_events(args):
            start = datetime.fromisoformat(args["start_date"])
            end = datetime.fromisoformat(args["end_date"])
            events = self._calendar.get_all_events(start, end, include_primary=True)
            # Convert events to a JSON-serializable form.
            payload = [
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
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "read_thread",
            "Read the full email thread for context on what's being scheduled.",
            {"thread_id": str},
        )
        async def read_thread(args):
            thread = self._gmail.get_thread(args["thread_id"])
            payload = [
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
            body = args["body"]
            content_type = "plain"

            # Check if branding is enabled for this user
            from scheduler.db import get_user_by_id

            user = get_user_by_id(self._user_id)
            if user and user.stash_branding_enabled:
                # Convert plain text to HTML and append branding
                html_body = html.escape(body).replace("\n", "<br>")
                html_body += '<br><br>sent by <a href="https://stash.ac">Stash</a>'
                body = html_body
                content_type = "html"

            draft_id = self._gmail.create_draft(
                thread_id=args["thread_id"],
                to=args["to"],
                subject=args["subject"],
                body=body,
                content_type=content_type,
            )
            draft_result["draft_id"] = draft_id

            # Store pending invite if requested
            if args.get("send_invite"):
                from scheduler.db import create_pending_invite

                create_pending_invite(
                    user_id=self._user_id,
                    thread_id=args["thread_id"],
                    attendee_email=args["invite_attendee_email"],
                    event_summary=args["invite_event_summary"],
                    event_start=datetime.fromisoformat(args["invite_event_start"]),
                    event_end=datetime.fromisoformat(args["invite_event_end"]),
                    add_google_meet=args.get("invite_add_google_meet", False),
                )

            return {"content": [{"type": "text", "text": json.dumps({"draft_id": draft_id})}]}

        @tool(
            "add_calendar_event",
            "Add an event to the user's stash calendar (e.g. when a time is confirmed but no invite exists).",
            {"summary": str, "start": str, "end": str, "description": str},
        )
        async def add_calendar_event(args):
            from scheduler.calendar.client import Event as CalEvent

            event = CalEvent(
                id=None,
                summary=args["summary"],
                start=datetime.fromisoformat(args["start"]),
                end=datetime.fromisoformat(args["end"]),
                description=args.get("description", ""),
                source="gmail",
            )
            event_id = self._calendar.add_event(event)
            return {"content": [{"type": "text", "text": json.dumps({"event_id": event_id})}]}

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
                body = args["body"]
                content_type = "plain"

                from scheduler.db import get_user_by_id

                user = get_user_by_id(self._user_id)
                if user and user.stash_branding_enabled:
                    html_body = html.escape(body).replace("\n", "<br>")
                    html_body += '<br><br>sent by <a href="https://stash.ac">Stash</a>'
                    body = html_body
                    content_type = "html"

                message_id = self._gmail.send_email(
                    thread_id=args["thread_id"],
                    to=args["to"],
                    subject=args["subject"],
                    body=body,
                    content_type=content_type,
                )
                draft_result["draft_id"] = f"sent:{message_id}"
                return {"content": [{"type": "text", "text": json.dumps({"message_id": message_id, "status": "sent"})}]}

            all_tools.append(send_email)

        return all_tools, draft_result

    def compose_and_create_draft(self, email: Email, classification: ClassificationResult) -> str | None:
        """Run the draft composer agent.

        The agent will:
        1. Read the full email thread for context
        2. Read calendar events to see what's already scheduled
        3. Reason about the user's real availability (including buffers,
           travel time, meal times, etc.)
        4. Compose a reply that matches the tone of the conversation
        5. Create the draft in Gmail

        Args:
            email: The incoming scheduling email.
            classification: The classification result with extracted details.

        Returns:
            The ID of the created Gmail draft, or None if the thread is
            already resolved and no draft was needed.
        """
        system_prompt = self._build_system_prompt()
        tools, draft_result = self._build_tools()
        server = create_sdk_mcp_server("draft-tools", tools=tools)

        # Initial instructions to the agent.
        classification_dict = {
            "intent": classification.intent.value,
            "confidence": classification.confidence,
            "summary": classification.summary,
            "proposed_times": classification.proposed_times,
            "participants": classification.participants,
            "duration_minutes": classification.duration_minutes,
        }

        prompt = (
            "You are a scheduling draft composer.\n\n"
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
            f"Message ID: {email.id}\n"
            f"Thread ID: {email.thread_id}\n"
            f"Sender: {email.sender}\n"
            f"Recipient: {email.recipient}\n"
            f"Subject: {email.subject}\n"
            f"Snippet: {email.snippet}\n\n"
            "Classification JSON:\n"
            f"{json.dumps(classification_dict, indent=2)}\n"
        )

        options = ClaudeAgentOptions(
            mcp_servers={"draft": server},
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",
            model="claude-opus-4-6",
        )

        # Run the agent; it will call tools via the MCP server.
        import asyncio
        import os

        # Allow nested Claude Code sessions (e.g. when server is launched from Claude Code)
        os.environ.pop("CLAUDECODE", None)

        async def _run_agent():
            import logging
            logger = logging.getLogger(__name__)

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
