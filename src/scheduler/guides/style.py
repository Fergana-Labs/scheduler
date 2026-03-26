"""Email Style guide-writer agent.

Analyzes past sent scheduling emails to learn how the user writes
scheduling-related emails, then writes a style guide for future agents.

Uses the Claude Agent SDK with custom tools (via an SDK MCP server).
"""

from __future__ import annotations

import json
import logging
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
    """Build the Agent SDK tools for the style agent."""

    @tool(
        "search_emails",
        "Search Gmail using a query string. Use from:me queries to find the user's sent emails.",
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
        "Read a full email thread to see the user's replies in context.",
        {"thread_id": str},
    )
    async def read_thread(args):
        result = backend.read_thread(args["thread_id"])
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    @tool(
        "write_guide",
        "Write the final email style guide. Call this once you've finished "
        "your analysis with the complete Markdown content.",
        {"content": str},
    )
    async def write_guide(args):
        result = backend.write_guide("email_style", args["content"])
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    return [search_emails, read_thread, write_guide]


STYLE_SYSTEM_PROMPT = """\
You are an analyst agent for a scheduling assistant. Your job is to study the \
user's past SENT scheduling emails and write a concrete style guide describing \
how they write scheduling-related emails.

Your process:
1. Search for the user's sent scheduling emails using queries like:
   - "from:me schedule"
   - "from:me meeting"
   - "from:me let's meet"
   - "from:me coffee"
   - "from:me call"
   - "from:me available"
   - "from:me free"
   - "from:me works for me"
   Try many variations to get a good sample.
2. Read full threads to see the user's replies in context (how they respond to \
scheduling requests, how they propose times, etc.).
3. Analyze the writing style:
   - Tone (casual, professional, warm, direct, etc.)
   - Formality level
   - Greeting style (Hi/Hey/Hello/Dear/none, first name vs full name)
   - Sign-off style (Best/Thanks/Cheers/none)
   - How they propose times (bullet list, inline, specific vs vague)
   - How they accept or decline
   - Typical email length
   - Common phrases or expressions they use
   - Punctuation habits (exclamation marks, ellipses, em dashes)
   - Use of pleasantries, small talk, or filler
4. Include real examples from actual emails (anonymize names/details if needed — \
replace with [Name], [Company], etc.).
5. Write a concrete Markdown guide addressed to a future AI agent that will be \
composing draft replies on behalf of this user.
6. Only report patterns you actually observe — note confidence levels.
7. Call write_guide with the final content when done.
"""


async def run_style_agent(backend: GuideBackend) -> None:
    """Run the email style guide-writer agent."""
    tools = _build_tools(backend)
    server = create_sdk_mcp_server("style-tools", tools=tools)

    prompt = (
        "Please analyze my sent scheduling emails and write an email style guide "
        "that a future AI agent can use to match my writing style when composing "
        "draft replies. Be thorough — search with many different queries."
    )

    options = ClaudeAgentOptions(
        mcp_servers={"style": server},
        system_prompt=STYLE_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        model="claude-sonnet-4-6",
        env={
            "ANTHROPIC_VERTEX_PROJECT_ID": config.gcp_project_id,
            "CLOUD_ML_REGION": config.gcp_region,
        },
    )

    print("Starting email style analysis...")
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
                        logger.error("style guide agent failed: %s", message.result)
                        raise RuntimeError(message.result)
                    print("\nEmail style guide written.")
