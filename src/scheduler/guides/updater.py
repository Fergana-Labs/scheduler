"""Guide Updater agents — continual learning from draft edit signals.

Runs weekly (triggered by POST /api/v1/guides/update-all).  Reads the past
week's composed_drafts where the user meaningfully edited before sending, then
proposes surgical changes to the style guide and scheduling preferences guide.

Two separate passes, each with its own agent and thresholds:
  - Style pass:       driven by text diffs alone;  frequency threshold = 3
  - Preferences pass: driven by diffs + thread context; threshold = 5

The agents output atomic proposed_changes rather than full rewrites, which
prevents slopification and gives a full audit trail.
"""

from __future__ import annotations

import json
import logging
import re
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

if TYPE_CHECKING:
    from scheduler.guides.backends import UpdaterBackend


logger = logging.getLogger(__name__)

# Minimum edited-draft count before running each pass.
STYLE_MIN_DRAFTS = 3
PREFERENCES_MIN_DRAFTS = 5

# Maximum allowed length growth ratio before a change is rejected.
MAX_LENGTH_GROWTH = 1.20


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _apply_change_to_guide(current: str, change: dict) -> str | None:
    """Apply a single atomic change to guide markdown. Returns new content or
    None if the change cannot be applied safely (e.g. section not found).

    Supports actions: 'modify', 'add', 'remove'.
    """
    action = change.get("action")
    section = change.get("section", "")
    proposed_text = change.get("proposed_text", "")
    current_text = change.get("current_text", "")

    if action == "modify":
        if current_text and current_text in current:
            return current.replace(current_text, proposed_text, 1)
        # Fuzzy: find the section header and append the change after it
        return None

    if action == "add":
        # Append to end of guide (or after a named section if section given)
        if section:
            # Try to insert after the last line of the named section header
            pattern = rf"(#+\s+{re.escape(section)}[^\n]*\n)"
            match = re.search(pattern, current, re.IGNORECASE)
            if match:
                insert_at = match.end()
                return current[:insert_at] + proposed_text + "\n" + current[insert_at:]
        return current.rstrip() + "\n\n" + proposed_text + "\n"

    if action == "remove":
        if current_text and current_text in current:
            return current.replace(current_text, "", 1)
        return None

    return None


def _guard_length(original: str, updated: str) -> bool:
    """Return True if the updated guide is within the allowed growth ratio."""
    if not original:
        return True
    return len(updated) <= len(original) * MAX_LENGTH_GROWTH


# ---------------------------------------------------------------------------
# Style updater agent
# ---------------------------------------------------------------------------

STYLE_UPDATER_SYSTEM_PROMPT = """\
You are a guide maintenance agent for a scheduling assistant. You receive:
1. The current Email Style Guide (markdown).
2. A list of before/after diffs — emails the assistant drafted that the user
   edited before sending.

Your job is to decide whether the style guide needs surgical updates based on
the observed edits.

## Process
1. Read each diff carefully. Look at what the user added, removed, or changed.
2. For each observed pattern, classify it as:
   - PERSISTENT: reflects a durable preference (e.g. greeting change, sign-off
     removal, consistent tone shift). These are candidates for guide changes.
   - EPHEMERAL: caused by one-time context (e.g. "I'm sick", "travelling this
     week", specific person preferences). These should NOT update the guide.
3. Count how many distinct diffs show the same pattern. Only propose a change
   if observed_n_times >= 3.
4. Propose atomic changes using propose_change. Each change must be targeted
   to a specific section — never propose a full rewrite.
5. If nothing warrants a change, call no_changes_needed with your reasoning.

## Rules
- Only report patterns you actually observe in the diffs provided.
- Do NOT invent patterns or extrapolate beyond the evidence.
- Each proposed change must have a concrete justification citing the diffs.
- Err on the side of no change over a speculative change.
"""


def _build_style_tools(backend: "UpdaterBackend") -> tuple[list, list]:
    proposed: list[dict] = []

    @tool(
        "propose_change",
        "Propose a surgical change to a specific section of the email style guide.",
        {
            "section": str,
            "action": str,
            "current_text": str,
            "proposed_text": str,
            "justification": str,
            "observed_n_times": int,
        },
    )
    async def propose_change(args):
        proposed.append({
            "section": args["section"],
            "action": args["action"],
            "current_text": args.get("current_text", ""),
            "proposed_text": args.get("proposed_text", ""),
            "justification": args["justification"],
            "observed_n_times": args["observed_n_times"],
            "applied": False,
        })
        return {"content": [{"type": "text", "text": json.dumps({"status": "recorded"})}]}

    @tool(
        "no_changes_needed",
        "Call this when the diffs do not justify any guide changes.",
        {"reason": str},
    )
    async def no_changes_needed(args):
        logger.info("style_updater: no changes needed — %s", args.get("reason", ""))
        return {"content": [{"type": "text", "text": json.dumps({"status": "no_change"})}]}

    return [propose_change, no_changes_needed], proposed


async def run_style_updater_agent(
    backend: "UpdaterBackend",
    edited_diffs: list[dict],
) -> list[dict]:
    """Run the style guide updater. Returns list of proposed_changes dicts."""
    current_guide = backend.load_guide("email_style") or ""

    diffs_text = _format_diffs(edited_diffs)

    prompt = (
        "Here is the current Email Style Guide:\n\n"
        f"{current_guide or '(no guide yet)'}\n\n"
        "---\n\n"
        f"Here are {len(edited_diffs)} edited drafts from the past week "
        "(original draft vs what the user actually sent):\n\n"
        f"{diffs_text}\n\n"
        "Please analyse the diffs and propose any warranted changes to the style guide. "
        "Remember: only propose changes seen 3+ times, and skip ephemeral edits."
    )

    tools, proposed = _build_style_tools(backend)
    server = create_sdk_mcp_server("style-updater-tools", tools=tools)
    options = ClaudeAgentOptions(
        mcp_servers={"updater": server},
        system_prompt=STYLE_UPDATER_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        model="claude-sonnet-4-6",
    )

    log_lines: list[str] = []
    with nested_claude_session():
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            log_lines.append(block.text)
                            logger.info("style_updater: %s", block.text)
                elif isinstance(message, ResultMessage):
                    if is_api_error_result(message.result):
                        logger.error("style_updater agent failed: %s", message.result)

    backend.set_agent_log("email_style", "\n".join(log_lines))
    return proposed


# ---------------------------------------------------------------------------
# Preferences updater agent
# ---------------------------------------------------------------------------

PREFERENCES_UPDATER_SYSTEM_PROMPT = """\
You are a guide maintenance agent for a scheduling assistant. You receive:
1. The current Scheduling Preferences Guide (markdown).
2. A list of before/after diffs — emails the assistant drafted that the user
   edited before sending, each with the full thread context.

Your job is to decide whether the scheduling preferences guide needs surgical
updates based on observed edits to proposed times, durations, and logistics.

## Process
1. Read each diff with its thread_context. Focus on changes to:
   - Proposed meeting times (morning vs afternoon, day of week)
   - Meeting duration (shorter/longer than suggested)
   - Location preferences
   - Urgency or advance-notice patterns
2. Classify each change as PERSISTENT or EPHEMERAL. Thread context clues for
   ephemeral: "I'm travelling", "sick", "just this once", "special case".
3. Only propose a change if observed_n_times >= 5 across distinct threads.
4. Call propose_change for each warranted update, or no_changes_needed.

## Rules
- Scheduling preferences are noisier than style — apply a higher bar.
- If the user's calendar was likely blocking a time that week, the change is
  probably ephemeral even if the same time was avoided multiple times.
- Never propose a full rewrite — only targeted section changes.
- Err on the side of no change over a speculative change.
"""


def _build_preferences_tools(backend: "UpdaterBackend") -> tuple[list, list]:
    proposed: list[dict] = []

    @tool(
        "propose_change",
        "Propose a surgical change to a specific section of the scheduling preferences guide.",
        {
            "section": str,
            "action": str,
            "current_text": str,
            "proposed_text": str,
            "justification": str,
            "observed_n_times": int,
        },
    )
    async def propose_change(args):
        proposed.append({
            "section": args["section"],
            "action": args["action"],
            "current_text": args.get("current_text", ""),
            "proposed_text": args.get("proposed_text", ""),
            "justification": args["justification"],
            "observed_n_times": args["observed_n_times"],
            "applied": False,
        })
        return {"content": [{"type": "text", "text": json.dumps({"status": "recorded"})}]}

    @tool(
        "no_changes_needed",
        "Call this when the diffs do not justify any guide changes.",
        {"reason": str},
    )
    async def no_changes_needed(args):
        logger.info("preferences_updater: no changes needed — %s", args.get("reason", ""))
        return {"content": [{"type": "text", "text": json.dumps({"status": "no_change"})}]}

    return [propose_change, no_changes_needed], proposed


async def run_preferences_updater_agent(
    backend: "UpdaterBackend",
    edited_diffs: list[dict],
) -> list[dict]:
    """Run the preferences guide updater. Returns list of proposed_changes dicts."""
    current_guide = backend.load_guide("scheduling_preferences") or ""
    diffs_text = _format_diffs(edited_diffs, include_thread_context=True)

    prompt = (
        "Here is the current Scheduling Preferences Guide:\n\n"
        f"{current_guide or '(no guide yet)'}\n\n"
        "---\n\n"
        f"Here are {len(edited_diffs)} edited drafts from the past week "
        "(original draft vs what the user sent, with thread context):\n\n"
        f"{diffs_text}\n\n"
        "Please analyse the diffs and propose any warranted changes to the scheduling "
        "preferences guide. Remember: only propose changes seen 5+ times across distinct "
        "threads, and skip ephemeral scheduling changes."
    )

    tools, proposed = _build_preferences_tools(backend)
    server = create_sdk_mcp_server("preferences-updater-tools", tools=tools)
    options = ClaudeAgentOptions(
        mcp_servers={"updater": server},
        system_prompt=PREFERENCES_UPDATER_SYSTEM_PROMPT,
        permission_mode="bypassPermissions",
        model="claude-sonnet-4-6",
    )

    log_lines: list[str] = []
    with nested_claude_session():
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            log_lines.append(block.text)
                            logger.info("preferences_updater: %s", block.text)
                elif isinstance(message, ResultMessage):
                    if is_api_error_result(message.result):
                        logger.error("preferences_updater agent failed: %s", message.result)

    backend.set_agent_log("scheduling_preferences", "\n".join(log_lines))
    return proposed


# ---------------------------------------------------------------------------
# Apply logic (frequency gate + length guard)
# ---------------------------------------------------------------------------

def apply_proposed_changes(
    guide_name: str,
    current_guide: str,
    proposed: list[dict],
    frequency_threshold: int,
) -> tuple[str, list[dict]]:
    """Apply proposed changes that pass the frequency gate and length guard.

    Returns (updated_guide_content, applied_changes_list).
    Changes that fail either check are left with applied=False.
    """
    updated = current_guide
    applied: list[dict] = []

    for change in proposed:
        if change.get("observed_n_times", 0) < frequency_threshold:
            change["skip_reason"] = (
                f"below frequency threshold "
                f"(need {frequency_threshold}, saw {change.get('observed_n_times', 0)})"
            )
            continue

        new_content = _apply_change_to_guide(updated, change)
        if new_content is None:
            change["skip_reason"] = "could not locate target text in guide"
            continue

        if not _guard_length(current_guide, new_content):
            change["skip_reason"] = (
                f"guide would grow beyond {int(MAX_LENGTH_GROWTH * 100)}% of original length"
            )
            continue

        updated = new_content
        change = dict(change)
        change["applied"] = True
        applied.append(change)

    return updated, applied


# ---------------------------------------------------------------------------
# Diff formatter helper
# ---------------------------------------------------------------------------

def _format_diffs(diffs: list[dict], include_thread_context: bool = False) -> str:
    parts = []
    for i, d in enumerate(diffs, 1):
        original = (d.get("raw_body") or d.get("original_body") or "").strip()
        sent = (d.get("sent_body") or "").strip()
        ratio = d.get("edit_distance_ratio", 0)
        added = d.get("chars_added", 0)
        removed = d.get("chars_removed", 0)

        part = (
            f"--- Diff {i} ---\n"
            f"Edit ratio: {ratio:.2f}  (+{added} chars / -{removed} chars)\n\n"
            f"ORIGINAL DRAFT:\n{original}\n\n"
            f"WHAT USER SENT:\n{sent}\n"
        )

        if include_thread_context and d.get("thread_context"):
            ctx = d["thread_context"]
            if isinstance(ctx, str):
                try:
                    ctx = json.loads(ctx)
                except Exception:
                    pass
            if isinstance(ctx, list) and ctx:
                ctx_lines = []
                for msg in ctx[-3:]:  # last 3 messages for brevity
                    sender = msg.get("sender", "?")
                    body = (msg.get("body") or "")[:200]
                    ctx_lines.append(f"  [{sender}]: {body}")
                part += "\nTHREAD CONTEXT (last 3 messages):\n" + "\n".join(ctx_lines) + "\n"

        parts.append(part)

    return "\n".join(parts)
