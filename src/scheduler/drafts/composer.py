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
        "description": "Create a draft reply in Gmail with the composed response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string", "description": "Thread to reply to"},
                "to": {"type": "string", "description": "Recipient email"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body text"},
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

    def __init__(self, gmail_client: GmailClient, calendar_client: CalendarClient, user_id: str):
        self._gmail = gmail_client
        self._calendar = calendar_client
        self._user_id = user_id

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
            "Create a draft reply in Gmail with the composed response.",
            {"thread_id": str, "to": str, "subject": str, "body": str},
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
            return {"content": [{"type": "text", "text": json.dumps({"draft_id": draft_id})}]}

        return [get_calendar_events, read_thread, create_draft], draft_result

    def compose_and_create_draft(self, email: Email, classification: ClassificationResult) -> str:
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
            The ID of the created Gmail draft.
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
            "2. Inspect the user's availability using get_calendar_events over a reasonable window "
            "(for example, the next 14 days).\n"
            "3. Propose concrete meeting times that respect the user's existing commitments and "
            "the extracted details from the classification.\n"
            "4. Create a natural-sounding draft reply using create_draft. "
            "When you are satisfied with the draft, call create_draft exactly once.\n\n"
            "Email summary (for quick reference):\n"
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

        if not draft_result.get("draft_id"):
            raise RuntimeError("Draft composer agent did not create a draft")

        return draft_result["draft_id"]
