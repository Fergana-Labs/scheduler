"""Scheduling Preferences guide-writer agent.

Analyzes past calendar events and Gmail scheduling threads to learn when
and how the user schedules things, then writes a guide for future agents.

Uses the Claude Agent SDK with custom tools (via an SDK MCP server).
"""

import json
import os
from datetime import datetime, timedelta

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
    """Build the Agent SDK tools for the preferences agent."""

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
        "get_calendar_events",
        "Get all events from the user's calendars (primary + stash) in a date range.",
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
        "write_guide",
        "Write the final scheduling preferences guide. Call this once you've finished "
        "your analysis with the complete Markdown content.",
        {"content": str},
    )
    async def write_guide(args):
        os.makedirs(config.guides_dir, exist_ok=True)
        path = os.path.join(config.guides_dir, "scheduling_preferences.md")
        with open(path, "w") as f:
            f.write(args["content"])
        return {"content": [{"type": "text", "text": json.dumps({"status": "written", "path": path})}]}

    return [search_emails, read_thread, get_calendar_events, write_guide]


PREFERENCES_SYSTEM_PROMPT = """\
You are an analyst agent for a scheduling assistant. Your job is to study the \
user's past calendar events and scheduling-related emails from the last \
{lookback_days} days and write a concrete guide describing their scheduling \
preferences and patterns.

Today's date: {today}
Analysis window: {window_start} to {today}

Your process:
1. Pull calendar events from the analysis window to see patterns in timing, \
duration, and frequency.
2. Search Gmail for scheduling threads — especially the user's sent replies \
where they propose or accept times.
3. Analyze the data for patterns:
   - Preferred times of day for different meeting types
   - Busy vs free days of the week
   - Typical meeting durations by type (1:1, group, meals, calls)
   - Buffer patterns between meetings
   - Protected blocks (lunch, focus time, mornings, evenings)
   - Recurring commitments
   - How far in advance they typically schedule
   - Any preferences they explicitly state in emails
4. Write a Markdown guide addressed to a future AI scheduling agent.
5. Only report patterns you actually observe — note confidence levels (strong \
pattern vs. weak signal). Do not fabricate patterns.
6. Call write_guide with the final content when done.
"""


async def run_preferences_agent(gmail: GmailClient, calendar: CalendarClient) -> None:
    """Run the scheduling preferences guide-writer agent."""
    today = datetime.now()
    window_start = today - timedelta(days=config.onboarding_lookback_days)

    system_prompt = PREFERENCES_SYSTEM_PROMPT.format(
        lookback_days=config.onboarding_lookback_days,
        today=today.strftime("%Y-%m-%d"),
        window_start=window_start.strftime("%Y-%m-%d"),
    )

    tools = _build_tools(gmail, calendar)
    server = create_sdk_mcp_server("preferences-tools", tools=tools)

    prompt = (
        f"Please analyze my calendar events and scheduling emails from the last "
        f"{config.onboarding_lookback_days} days and write a scheduling preferences "
        f"guide. Be thorough in your analysis."
    )

    options = ClaudeAgentOptions(
        mcp_servers={"preferences": server},
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        model="claude-opus-4-6",
    )

    print("Starting scheduling preferences analysis...")
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print("\nScheduling preferences guide written.")
