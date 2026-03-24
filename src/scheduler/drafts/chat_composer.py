"""Chat draft composer — generates chat reply drafts for scheduling messages.

Follows the DraftBackend Protocol pattern from composer.py. Instead of reading
Gmail threads and creating Gmail drafts, this reads Matrix room messages and
writes to the pending_replies table for user review.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

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
    from scheduler.matrix.client import MatrixClient

import os

logger = logging.getLogger(__name__)


class ChatDraftBackend:
    """Draft backend for chat messages — reads Matrix rooms, writes to pending_replies."""

    def __init__(self, matrix_client: MatrixClient, user_id: str):
        self._matrix = matrix_client
        self._user_id = user_id

    def load_guide(self, name: str) -> str | None:
        from scheduler.guides import load_guide

        return load_guide(name, user_id=self._user_id)

    def get_user_timezone(self) -> str:
        """Get user timezone from their calendar settings."""
        try:
            from scheduler.auth.google_auth import load_credentials
            from scheduler.calendar.client import CalendarClient
            from scheduler.config import config

            creds = load_credentials(self._user_id)
            calendar = CalendarClient(creds, config.scheduled_calendar_name)
            return calendar.get_user_timezone()
        except Exception:
            logger.warning("chat_composer: failed to get user timezone, defaulting to UTC")
            return "UTC"

    def get_calendar_events(self, start_date: str, end_date: str) -> list[dict]:
        """Get calendar events for availability checking."""
        try:
            from scheduler.auth.google_auth import load_credentials
            from scheduler.calendar.client import CalendarClient
            from scheduler.config import config
            from scheduler.db import get_user_by_id

            user = get_user_by_id(self._user_id)
            creds = load_credentials(self._user_id)
            calendar = CalendarClient(
                creds,
                config.scheduled_calendar_name,
                extra_calendar_ids=user.calendar_ids or [] if user else [],
            )

            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            events = calendar.get_all_events(start, end, include_primary=True)
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
        except Exception:
            logger.warning("chat_composer: failed to get calendar events")
            return []

    def read_thread(self, room_id: str) -> list[dict]:
        """Read recent messages from a Matrix room for context."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context — schedule and wait via a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                messages = pool.submit(
                    asyncio.run,
                    self._matrix.get_room_messages(room_id, limit=20),
                ).result()
        else:
            messages = asyncio.run(
                self._matrix.get_room_messages(room_id, limit=20)
            )

        return [
            {
                "event_id": m.event_id,
                "sender": m.sender_display_name,
                "body": m.body,
                "timestamp": m.timestamp.isoformat(),
                "platform": m.platform,
            }
            for m in messages
        ]

    def create_draft(self, args: dict) -> dict:
        """Create a pending reply in the database for user review."""
        from scheduler.db import create_pending_reply

        pending_reply = create_pending_reply(
            user_id=self._user_id,
            platform=args["platform"],
            room_id=args["room_id"],
            sender_name=args["sender_name"],
            conversation_context=args.get("conversation_context"),
            proposed_reply=args["body"],
        )
        return {"pending_reply_id": pending_reply.id}


def _classification_dict(classification: ClassificationResult | dict) -> dict:
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


class ChatDraftComposer:
    """Agent that composes draft replies for chat scheduling messages."""

    def __init__(self, backend: ChatDraftBackend, user_id: str):
        self._backend = backend
        self._user_id = user_id

    def _build_system_prompt(self) -> str:
        parts = [
            "You are a draft composer agent for a scheduling assistant. "
            "Your job is to read the chat conversation, check the user's calendar "
            "for availability, and compose a short, conversational reply."
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
                "\n\n## Communication Style Guide (adapt for chat)\n"
                "The user's general communication style is shown below. Adapt it to be "
                "more casual and conversational for chat — shorter sentences, less formal:\n\n"
                + email_style
            )

        parts.append(
            "\n\n## Chat Reply Guidelines\n"
            "- Keep replies SHORT — 1-3 sentences max, like a real chat message.\n"
            "- Be casual and conversational, not formal.\n"
            "- Don't use email conventions (no \"Dear\", \"Best regards\", etc.).\n"
            "- Match the tone of the conversation.\n"
            "- Be warm, friendly, and accommodating — never passive-aggressive.\n"
            "- Don't express frustration about scheduling difficulty."
        )

        return "\n".join(parts)

    def _build_tools(
        self, room_id: str, sender_name: str, platform: str
    ) -> tuple[list, dict]:
        draft_result: dict = {"pending_reply_id": None}

        @tool(
            "get_calendar_events",
            "Get all events from the user's calendars in a date range. "
            "Use this to see what the user already has scheduled.",
            {"start_date": str, "end_date": str},
        )
        async def get_calendar_events(args):
            payload = self._backend.get_calendar_events(args["start_date"], args["end_date"])
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "read_conversation",
            "Read the recent chat conversation for context on what's being discussed.",
            {"room_id": str},
        )
        async def read_conversation(args):
            payload = self._backend.read_thread(args["room_id"])
            return {"content": [{"type": "text", "text": json.dumps(payload)}]}

        @tool(
            "create_draft_reply",
            "Create a draft chat reply for the user to review before sending.",
            {"body": str},
        )
        async def create_draft_reply(args):
            # Read conversation context for storage
            context = self._backend.read_thread(room_id)
            result = self._backend.create_draft({
                "platform": platform,
                "room_id": room_id,
                "sender_name": sender_name,
                "conversation_context": context,
                "body": args["body"],
            })
            draft_result["pending_reply_id"] = result.get("pending_reply_id")
            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        return [get_calendar_events, read_conversation, create_draft_reply], draft_result

    def compose_and_create_draft(
        self,
        room_id: str,
        sender_name: str,
        platform: str,
        classification: ClassificationResult | dict,
        batch_text: str,
        current_datetime: str | None = None,
    ) -> str | None:
        """Compose a draft chat reply and save it as a pending reply.

        Args:
            room_id: The Matrix room ID.
            sender_name: Display name of the person who sent the message.
            platform: Source platform (whatsapp, instagram, etc.).
            classification: The classification result from classify_chat_message().
            batch_text: The concatenated message text to respond to.
            current_datetime: Optional current datetime string for the prompt.

        Returns:
            The pending_reply_id if a draft was created, None otherwise.
        """
        system_prompt = self._build_system_prompt()
        tools, draft_result = self._build_tools(room_id, sender_name, platform)
        server = create_sdk_mcp_server("chat-draft-tools", tools=tools)
        classification_dict = _classification_dict(classification)

        user_timezone = self._backend.get_user_timezone()

        datetime_line = (
            f"The current date and time is {current_datetime}.\n\n"
            if current_datetime
            else ""
        )

        prompt = (
            "You are a chat scheduling draft composer.\n\n"
            + datetime_line
            + f"The user's timezone is {user_timezone}.\n\n"
            f"Platform: {platform}\n"
            f"Room ID: {room_id}\n\n"
            "You are given a chat message that has been classified as scheduling-related. "
            "Your job is to:\n"
            "1. Read the conversation using read_conversation to understand the full context.\n"
            "2. Check the user's calendar availability using get_calendar_events over "
            "a reasonable window (e.g. the next 14 days).\n"
            "3. Compose a SHORT, CASUAL chat reply proposing times or responding appropriately.\n"
            "4. Create the draft using create_draft_reply.\n\n"
            "IMPORTANT: This is a CHAT reply, not an email. Keep it short (1-3 sentences), "
            "casual, and conversational. No formal greetings or sign-offs.\n\n"
            f"Message from {sender_name}:\n{batch_text}\n\n"
            "Classification JSON:\n"
            f"{json.dumps(classification_dict, indent=2)}\n"
        )

        options = ClaudeAgentOptions(
            mcp_servers={"chat-draft": server},
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",
            model="claude-sonnet-4-6",
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
                                logger.info("chat_composer: %s", block.text)
                    elif isinstance(message, ResultMessage):
                        logger.info("chat_composer result: %s", message.result)
                    else:
                        logger.info("chat_composer message: %s", type(message).__name__)
            finally:
                await client.disconnect()

        asyncio.run(_run_agent())
        return draft_result.get("pending_reply_id") or None
