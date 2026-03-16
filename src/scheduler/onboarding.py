"""Onboarding agent — backfills the stash calendar from Gmail history.

This is an AGENT (not a simple LLM completion). It uses the Claude Agent SDK
with custom tools (via an SDK MCP server) to agentically search through Gmail,
read email threads, check for existing calendar events, and add missing
commitments to the stash calendar.

An agent is used here (rather than a single completion) because onboarding
requires iterative exploration — the agent needs to search Gmail with different
queries, read through threads to understand context, decide which emails
represent real commitments, and cross-reference with the calendar. This is
too complex and variable for a single LLM call.

Designed to run in the cloud via e2b.
"""

import json
from datetime import datetime, timedelta

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

from scheduler.auth.google_auth import get_credentials
from scheduler.calendar.client import CalendarClient, Event
from scheduler.config import config
from scheduler.gmail.client import GmailClient


def _serialize_email(email):
    """Serialize an Email object to a dict for the agent."""
    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "sender": email.sender,
        "recipient": email.recipient,
        "subject": email.subject,
        "body": email.body,
        "date": email.date.isoformat(),
        "snippet": email.snippet,
    }


def _serialize_event(event):
    """Serialize an Event object to a dict for the agent."""
    return {
        "id": event.id,
        "summary": event.summary,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "description": event.description,
    }


def _build_tools(gmail: GmailClient, calendar: CalendarClient):
    """Build the Agent SDK tools backed by real Gmail/Calendar clients."""

    events_added = {"count": 0}

    @tool(
        "search_emails",
        "Search Gmail using a query string. Use this to find scheduling-related emails.",
        {"query": str, "max_results": int},
    )
    async def search_emails(args):
        emails = gmail.search(
            query=args["query"],
            max_results=args.get("max_results", 50),
        )
        result = json.dumps({"emails": [_serialize_email(e) for e in emails]})
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "read_thread",
        "Read a full email thread to understand the context of a scheduling conversation.",
        {"thread_id": str},
    )
    async def read_thread(args):
        thread_messages = gmail.get_thread(args["thread_id"])
        result = json.dumps({"messages": [_serialize_email(e) for e in thread_messages]})
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "check_calendar",
        "Check if a calendar event already exists in the given time range. "
        "Returns the event if found, null if not.",
        {"summary": str, "start_date": str, "end_date": str},
    )
    async def check_calendar(args):
        event = calendar.find_event(
            summary=args["summary"],
            time_min=datetime.fromisoformat(args["start_date"]),
            time_max=datetime.fromisoformat(args["end_date"]),
        )
        if event:
            result = json.dumps({"exists": True, "event": _serialize_event(event)})
        else:
            result = json.dumps({"exists": False, "event": None})
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "get_calendar_events",
        "Get all events from the user's calendars (primary + stash) in a date range. "
        "Use this to see what's already on the calendar.",
        {"start_date": str, "end_date": str},
    )
    async def get_calendar_events(args):
        events = calendar.get_all_events(
            time_min=datetime.fromisoformat(args["start_date"]),
            time_max=datetime.fromisoformat(args["end_date"]),
        )
        result = json.dumps({"events": [_serialize_event(e) for e in events]})
        return {"content": [{"type": "text", "text": result}]}

    @tool(
        "add_to_stash_calendar",
        "Add a commitment to the stash calendar.",
        {"summary": str, "start": str, "end": str, "description": str},
    )
    async def add_to_stash_calendar(args):
        event = Event(
            id=None,
            summary=args["summary"],
            start=datetime.fromisoformat(args["start"]),
            end=datetime.fromisoformat(args["end"]),
            description=args.get("description", ""),
            source="gmail",
        )
        event_id = calendar.add_event(event)
        events_added["count"] += 1
        print(f"  Added: {event.summary} ({event.start.strftime('%b %d %I:%M %p')})")
        result = json.dumps({"event_id": event_id, "status": "created"})
        return {"content": [{"type": "text", "text": result}]}

    return (
        [search_emails, read_thread, check_calendar, get_calendar_events, add_to_stash_calendar],
        events_added,
    )


ONBOARDING_SYSTEM_PROMPT = """\
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
- When you've exhausted your search queries and feel confident you've found \
the major commitments, stop.
"""


async def _run_onboarding_async():
    """Async implementation of the onboarding agent."""
    creds = get_credentials()
    gmail = GmailClient(creds)
    calendar = CalendarClient(creds, config.stash_calendar_name)
    calendar.get_or_create_stash_calendar()

    today = datetime.now()
    window_start = today - timedelta(days=config.onboarding_lookback_days)

    system_prompt = ONBOARDING_SYSTEM_PROMPT.format(
        lookback_days=config.onboarding_lookback_days,
        today=today.strftime("%Y-%m-%d"),
        window_start=window_start.strftime("%Y-%m-%d"),
    )

    tools, events_added = _build_tools(gmail, calendar)
    server = create_sdk_mcp_server("onboarding-tools", tools=tools)

    prompt = (
        f"Please search through my Gmail from the last "
        f"{config.onboarding_lookback_days} days and add any "
        f"commitments you find to my stash calendar. Be thorough."
    )

    options = ClaudeAgentOptions(
        mcp_servers={"onboarding": server},
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        model="claude-opus-4-6",
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print(f"\nOnboarding complete. {events_added['count']} events added.")
                if message.result:
                    print(f"Agent summary: {message.result}")


def run_onboarding():
    """Run the onboarding agent to backfill the stash calendar.

    Launches a Claude agent with Gmail and Calendar tools. The agent will:
    1. Search Gmail with various queries to find scheduling-related emails
    2. Read threads to understand the full context of each conversation
    3. Determine which emails represent real commitments the user agreed to
    4. Cross-reference with existing calendar events to avoid duplicates
    5. Add missing commitments to the stash calendar
    """
    anyio.run(_run_onboarding_async)


if __name__ == "__main__":
    run_onboarding()
