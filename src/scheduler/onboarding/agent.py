"""Calendar backfill agent — searches Gmail history and populates the stash calendar."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

from scheduler.claude_runtime import is_api_error_result, nested_claude_session

if TYPE_CHECKING:
    from scheduler.onboarding.backends import BackfillBackend


logger = logging.getLogger(__name__)


BACKFILL_SYSTEM_PROMPT = """\
You are an onboarding agent for a scheduling assistant. Your job is to search \
through the user's Gmail history from the last {lookback_days} days and find \
commitments — meetings, calls, dinners, events, etc. — that the user has \
agreed to. For each real commitment you find, check if it already exists on \
the calendar, and if not, add it to the stash calendar.

Today's date: {today}
Search window: {window_start} to {today}

Guidelines:
- Search Gmail with a variety of queries to find scheduling-related emails \
(e.g. "let's meet", "schedule a call", "dinner", "coffee", "zoom link", \
"calendar invite", etc.). Be thorough — try many different search terms.
- Read the full thread for each promising result to understand context.
- Only add events where the user clearly agreed to or initiated a commitment. \
Skip tentative/declined/cancelled plans.
- Before adding anything, use check_calendar to avoid duplicates.
- Extract the best date/time you can from the thread. If a time was agreed \
but is ambiguous, make your best estimate and note the uncertainty in the \
description.
- Set reasonable durations (30 min for calls, 1 hour for meetings, 1.5-2 \
hours for meals, etc.) when the duration isn't specified.
- Include context in the event description: who it's with, what it's about, \
and the source email subject.
- Note any location information from threads (office address, restaurant, \
coffee shop, Zoom/Meet link, etc.) and include it in the event description. \
Track frequently mentioned locations as they indicate user preferences.
- When you've exhausted your search queries and feel confident you've found \
the major commitments, stop.
"""


def _build_tools(backend: BackfillBackend):
    """Build Agent SDK tools backed by the given backend."""

    events_added = {"count": 0}

    @tool(
        "search_emails",
        "Search Gmail using a query string. Use this to find scheduling-related emails.",
        {"query": str, "max_results": int},
    )
    async def search_emails(args):
        result = backend.search_emails(
            query=args["query"],
            max_results=args.get("max_results", 50),
        )
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool(
        "read_thread",
        "Read a full email thread to understand the context of a scheduling conversation.",
        {"thread_id": str},
    )
    async def read_thread(args):
        result = backend.read_thread(args["thread_id"])
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool(
        "check_calendar",
        "Check if a calendar event already exists in the given time range. "
        "Returns the event if found, null if not.",
        {"summary": str, "start_date": str, "end_date": str},
    )
    async def check_calendar(args):
        result = backend.find_event(
            summary=args["summary"],
            start_date=args["start_date"],
            end_date=args["end_date"],
        )
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool(
        "get_calendar_events",
        "Get all events from the user's calendars (primary + stash) in a date range. "
        "Use this to see what's already on the calendar.",
        {"start_date": str, "end_date": str},
    )
    async def get_calendar_events(args):
        result = backend.get_calendar_events(
            start_date=args["start_date"],
            end_date=args["end_date"],
        )
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool(
        "add_to_stash_calendar",
        "Add a commitment to the stash calendar.",
        {"summary": str, "start": str, "end": str, "description": str},
    )
    async def add_to_stash_calendar(args):
        result = backend.add_event(
            summary=args["summary"],
            start=args["start"],
            end=args["end"],
            description=args.get("description", ""),
        )
        events_added["count"] += 1
        print(f"  Added: {args['summary']} ({args['start']})")
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    return (
        [search_emails, read_thread, check_calendar, get_calendar_events, add_to_stash_calendar],
        events_added,
    )


async def _run_backfill_async(backend: BackfillBackend, lookback_days: int):
    """Async implementation of the calendar backfill agent."""
    today = datetime.now()
    window_start = today - timedelta(days=lookback_days)

    system_prompt = BACKFILL_SYSTEM_PROMPT.format(
        lookback_days=lookback_days,
        today=today.strftime("%Y-%m-%d"),
        window_start=window_start.strftime("%Y-%m-%d"),
    )

    tools, events_added = _build_tools(backend)
    server = create_sdk_mcp_server("onboarding-tools", tools=tools)

    prompt = (
        f"Please search through my Gmail from the last "
        f"{lookback_days} days and add any "
        f"commitments you find to my stash calendar. Be thorough."
    )

    options = ClaudeAgentOptions(
        mcp_servers={"onboarding": server},
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        model="claude-sonnet-4-6",
    )

    with nested_claude_session():
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)
                elif isinstance(message, ResultMessage):
                    if is_api_error_result(message.result):
                        logger.error("onboarding backfill agent failed: %s", message.result)
                        raise RuntimeError(message.result)
                    print(f"\nBackfill complete. {events_added['count']} events added.")
                    if message.result:
                        print(f"Agent summary: {message.result}")


def run_backfill_agent(backend: BackfillBackend, lookback_days: int):
    """Run the calendar backfill agent with the given backend."""
    anyio.run(_run_backfill_async, backend, lookback_days)
