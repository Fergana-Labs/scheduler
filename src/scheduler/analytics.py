"""Backend analytics module — tracks user engagement and draft editing behavior."""

import logging
import threading

logger = logging.getLogger(__name__)


def track(user_id: str, event: str, properties: dict | None = None) -> None:
    """Fire-and-forget: insert an analytics event in a daemon thread."""

    def _insert():
        try:
            from scheduler.db import insert_analytics_event

            insert_analytics_event(user_id, event, properties)
        except Exception:
            logger.debug("analytics.track: failed to insert event %s", event, exc_info=True)

    t = threading.Thread(target=_insert, daemon=True)
    t.start()


def record_draft_composed(
    user_id: str,
    thread_id: str,
    draft_id: str,
    thread_messages: list[dict],
    subject: str,
    body: str,
    was_autopilot: bool = False,
) -> None:
    """Store a composed draft record. Runs in a daemon thread."""

    def _store():
        try:
            from scheduler.db import store_composed_draft

            store_composed_draft(
                user_id=user_id,
                thread_id=thread_id,
                draft_id=draft_id,
                thread_context=thread_messages,
                subject=subject,
                body=body,
                was_autopilot=was_autopilot,
            )
        except Exception:
            logger.debug("analytics.record_draft_composed: failed for thread %s", thread_id, exc_info=True)

    t = threading.Thread(target=_store, daemon=True)
    t.start()


def record_draft_sent(
    user_id: str,
    thread_id: str,
    sent_body: str,
    sent_at,
) -> None:
    """Look up the composed draft, compute diff metrics, and update. Runs in a daemon thread."""

    def _update():
        try:
            import difflib

            from scheduler.db import get_composed_draft_by_thread, update_composed_draft_sent

            row = get_composed_draft_by_thread(user_id, thread_id)
            if not row:
                return

            original = row["original_body"]

            # Normalize whitespace before comparing to ignore Gmail formatting artifacts
            original_norm = " ".join(original.split())
            sent_norm = " ".join(sent_body.split())
            matcher = difflib.SequenceMatcher(None, original_norm, sent_norm)
            similarity = matcher.ratio()

            was_edited = similarity < 0.98
            edit_distance_ratio = 1.0 - similarity

            # Compute chars added and removed from opcodes
            chars_added = 0
            chars_removed = 0
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "replace":
                    chars_removed += i2 - i1
                    chars_added += j2 - j1
                elif tag == "delete":
                    chars_removed += i2 - i1
                elif tag == "insert":
                    chars_added += j2 - j1

            update_composed_draft_sent(
                draft_id=row["id"],
                sent_body=sent_body,
                was_edited=was_edited,
                edit_distance_ratio=edit_distance_ratio,
                chars_added=chars_added,
                chars_removed=chars_removed,
                sent_at=sent_at,
            )

            track(user_id, "draft_sent", {
                "thread_id": thread_id,
                "was_edited": was_edited,
                "edit_distance_ratio": round(edit_distance_ratio, 4),
                "chars_added": chars_added,
                "chars_removed": chars_removed,
                "was_autopilot": row.get("was_autopilot", False),
            })
        except Exception:
            logger.debug("analytics.record_draft_sent: failed for thread %s", thread_id, exc_info=True)

    t = threading.Thread(target=_update, daemon=True)
    t.start()
