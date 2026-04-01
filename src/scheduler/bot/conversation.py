"""Bot conversation state machine.

Tracks the lifecycle of a scheduling conversation between the bot and
a counterparty, on behalf of a registered user.

States:
    new         → Bot just received the first CC. Hasn't replied yet.
    proposing   → Bot sent proposed times, waiting for reply.
    negotiating → Counterparty replied (declined, counterproposed, asked question).
    confirmed   → Time agreed, calendar invite sent.
    done        → Event created, conversation complete.
    cancelled   → Meeting cancelled or thread went cold.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from scheduler.db import (
    BotConversationRow,
    update_bot_conversation,
)

logger = logging.getLogger(__name__)

# Valid state transitions
_TRANSITIONS: dict[str, set[str]] = {
    "new": {"proposing", "confirmed", "cancelled"},
    "proposing": {"negotiating", "confirmed", "cancelled"},
    "negotiating": {"proposing", "negotiating", "confirmed", "cancelled"},
    "confirmed": {"done", "cancelled"},
    "done": set(),
    "cancelled": set(),
}


def transition(conversation: BotConversationRow, new_state: str) -> None:
    """Advance a conversation to a new state with validation."""
    allowed = _TRANSITIONS.get(conversation.state, set())
    if new_state not in allowed:
        logger.warning(
            "bot_conversation: invalid transition %s → %s for conversation=%s",
            conversation.state, new_state, conversation.id,
        )
        return

    kwargs: dict = {"state": new_state}
    if new_state in ("done", "cancelled"):
        kwargs["resolved_at"] = datetime.now(timezone.utc)

    update_bot_conversation(conversation.id, **kwargs)
    logger.info(
        "bot_conversation: %s → %s for conversation=%s (thread=%s)",
        conversation.state, new_state, conversation.id, conversation.thread_id,
    )


def record_bot_reply(
    conversation: BotConversationRow,
    proposed_windows: list[dict] | None = None,
) -> None:
    """Record that the bot sent a reply in this conversation."""
    now = datetime.now(timezone.utc)
    kwargs: dict = {
        "turn_count": conversation.turn_count + 1,
        "last_bot_reply_at": now,
    }

    if proposed_windows:
        # Merge new proposals with existing, deduplicating
        existing = conversation.proposed_windows or []
        all_windows = existing + proposed_windows
        kwargs["proposed_windows"] = all_windows

    update_bot_conversation(conversation.id, **kwargs)


def record_declined_times(
    conversation: BotConversationRow,
    declined: list[dict],
) -> None:
    """Record times that the counterparty said don't work."""
    existing = conversation.declined_windows or []
    update_bot_conversation(
        conversation.id,
        declined_windows=existing + declined,
    )


def record_constraint(
    conversation: BotConversationRow,
    constraint: str,
) -> None:
    """Record a constraint the counterparty mentioned (e.g. 'prefers mornings')."""
    existing = conversation.constraints or []
    if constraint not in existing:
        update_bot_conversation(
            conversation.id,
            constraints=existing + [constraint],
        )


def build_conversation_context(conversation: BotConversationRow) -> str:
    """Build a text summary of conversation state for the agent.

    This is injected into the agent prompt so it knows what has already
    been proposed, declined, and learned.
    """
    parts = []

    parts.append(f"Conversation state: {conversation.state}")
    parts.append(f"Turn count: {conversation.turn_count}")

    if conversation.event_summary:
        parts.append(f"Meeting topic: {conversation.event_summary}")
    if conversation.duration_minutes:
        parts.append(f"Expected duration: {conversation.duration_minutes} minutes")

    if conversation.proposed_windows:
        parts.append("\nPreviously proposed times (DO NOT re-propose these):")
        for w in conversation.proposed_windows:
            parts.append(f"  - {w.get('date', '?')} {w.get('start', '?')} - {w.get('end', '?')}")

    if conversation.declined_windows:
        parts.append("\nTimes the counterparty said DON'T work (NEVER suggest these):")
        for w in conversation.declined_windows:
            parts.append(f"  - {w.get('date', '?')} {w.get('start', '?')} - {w.get('end', '?')}")

    if conversation.constraints:
        parts.append("\nKnown constraints:")
        for c in conversation.constraints:
            parts.append(f"  - {c}")

    return "\n".join(parts)
