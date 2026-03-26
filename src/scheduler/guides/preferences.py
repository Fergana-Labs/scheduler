"""Scheduling Preferences guide-writer agent.

Analyzes past calendar events and Gmail scheduling threads to learn when
and how the user schedules things, then writes a guide for future agents.

Uses the Claude Agent SDK with custom tools (via an SDK MCP server).
"""

from __future__ import annotations

import json
import logging
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

from scheduler.claude_runtime import is_api_error_result, nested_claude_session
from scheduler.config import config

if TYPE_CHECKING:
    from scheduler.guides.backends import GuideBackend


logger = logging.getLogger(__name__)


def _build_tools(backend: GuideBackend):
    """Build the Agent SDK tools for the preferences agent."""

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
        "get_calendar_events",
        "Get all events from the user's calendars (primary + scheduled) in a date range.",
        {"start_date": str, "end_date": str},
    )
    async def get_calendar_events(args):
        result = backend.get_calendar_events(
            start_date=args["start_date"],
            end_date=args["end_date"],
        )
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool(
        "write_guide",
        "Write the final scheduling preferences guide. Call this once you've finished "
        "your analysis with the complete Markdown content.",
        {"content": str},
    )
    async def write_guide(args):
        result = backend.write_guide("scheduling_preferences", args["content"])
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

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
   - Preferred in-person meeting locations (coffee shops, restaurants, offices)
   - Location patterns by meeting type (e.g. coffee for 1:1s, office for team meetings)
   - In-person vs. virtual preference
   - Common video conferencing tools (Zoom, Google Meet, Teams, etc.)
   - Geographic patterns (neighborhoods, areas of the city frequently used)
   - Prioritization patterns: which meeting types take precedence over others \
(e.g. work vs personal, external vs internal, 1:1s vs group)
   - How the user handles scheduling conflicts — do they reschedule, decline, \
or double-book? Which events get moved and which are immovable?
   - Urgency signals: how quickly they respond to different types of requests, \
language patterns that indicate high vs low priority
   - Flexibility hierarchy: which calendar blocks are firm vs. negotiable
4. Write a Markdown guide addressed to a future AI scheduling agent.
5. Only report patterns you actually observe — note confidence levels (strong \
pattern vs. weak signal). Do not fabricate patterns.
6. Anonymize the guide: replace specific people's names with generic labels \
(e.g., "[coworker]", "[manager]"), replace specific meeting names with types \
(e.g., "weekly team sync" → "recurring team meeting"), and never include \
email subjects or company names. The guide should capture patterns and \
preferences, not a dossier of who the user meets with.
7. Call write_guide with the final content when done.
"""


async def run_preferences_agent(backend: GuideBackend) -> None:
    """Run the scheduling preferences guide-writer agent."""
    today = datetime.now()
    window_start = today - timedelta(days=config.onboarding_lookback_days)

    system_prompt = PREFERENCES_SYSTEM_PROMPT.format(
        lookback_days=config.onboarding_lookback_days,
        today=today.strftime("%Y-%m-%d"),
        window_start=window_start.strftime("%Y-%m-%d"),
    )

    tools = _build_tools(backend)
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
        model="claude-sonnet-4-6",
    )

    print("Starting scheduling preferences analysis...")
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
                        logger.error("preferences guide agent failed: %s", message.result)
                        raise RuntimeError(message.result)
                    print("\nScheduling preferences guide written.")
