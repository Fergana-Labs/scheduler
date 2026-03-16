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

import anthropic

from scheduler.calendar.client import CalendarClient
from scheduler.classifier.intent import ClassificationResult
from scheduler.config import config
from scheduler.gmail.client import Email, GmailClient


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

    def __init__(self, gmail_client: GmailClient, calendar_client: CalendarClient):
        self._gmail = gmail_client
        self._calendar = calendar_client

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
        # TODO: Implement agentic loop
        # 1. Build the system prompt with user preferences and context
        # 2. Start the agent with the email + classification as the initial message
        # 3. Run the agentic loop:
        #    - Agent calls get_calendar_events → we call CalendarClient.get_all_events()
        #    - Agent calls read_thread → we call GmailClient.get_thread()
        #    - Agent calls create_draft → we call GmailClient.create_draft()
        # 4. Return the draft ID from the create_draft tool call
        raise NotImplementedError

    def _handle_tool_call(self, tool_name: str, tool_input: dict):
        """Route agent tool calls to the appropriate service."""
        # TODO: Implement tool call routing
        # - "get_calendar_events" → self._calendar.get_all_events(...)
        # - "read_thread" → self._gmail.get_thread(...)
        # - "create_draft" → self._gmail.create_draft(...)
        raise NotImplementedError
