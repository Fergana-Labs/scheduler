"""Backend analytics module — tracks user engagement and draft editing behavior."""

import difflib
import html
import logging
import re
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
    refresh_count: int = 0,
    suggested_windows: list[dict] | None = None,
) -> None:
    """Anonymize and store a composed draft. Runs in a daemon thread."""

    def _store():
        try:
            from scheduler.anonymize import anonymize_draft_context
            from scheduler.db import store_composed_draft

            # Strip HTML so original body is plain text (matches sent body processing)
            plain_body = re.sub(r'<br\s*/?>', '\n', body)
            plain_body = re.sub(r'<[^>]+>', '', plain_body)
            plain_body = html.unescape(plain_body)

            anon_thread, anon_body, anon_subject = anonymize_draft_context(
                thread_messages, plain_body, subject
            )
            store_composed_draft(
                user_id=user_id,
                thread_id=thread_id,
                draft_id=draft_id,
                thread_context=anon_thread,
                subject=anon_subject,
                body=anon_body,
                was_autopilot=was_autopilot,
                raw_body=plain_body,
                refresh_count=refresh_count,
                suggested_windows=suggested_windows,
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
    message_id: str | None = None,
    sender: str | None = None,
) -> None:
    """Look up the composed draft, compute diff metrics, and update. Runs in a daemon thread."""

    def _update():
        try:
            from scheduler.anonymize import anonymize_text
            from scheduler.db import get_composed_draft_by_thread, update_composed_draft_sent

            row = get_composed_draft_by_thread(user_id, thread_id)
            if not row:
                return

            # Strip HTML tags so sent body matches the plain-text original for diffing
            plain_sent = re.sub(r'<br\s*/?>', '\n', sent_body)
            plain_sent = re.sub(r'<[^>]+>', '', plain_sent)
            plain_sent = html.unescape(plain_sent)

            # Diff against raw (pre-anonymization) body to avoid mismatched placeholders
            # Fall back to anonymized original_body for older drafts without raw_body
            original_raw = row.get("raw_body") or row["original_body"]

            # Normalize whitespace before comparing to ignore Gmail formatting artifacts
            original_norm = " ".join(original_raw.split())
            sent_norm = " ".join(plain_sent.split())
            matcher = difflib.SequenceMatcher(None, original_norm, sent_norm)
            similarity = matcher.ratio()

            # If the sent message is too different from the composed draft,
            # it's likely a different message on the same thread — skip it
            if similarity < 0.3:
                logger.debug("analytics.record_draft_sent: sent body too different (%.1f%% match), skipping thread %s", similarity * 100, thread_id)
                return

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

            # Anonymize sent body for display only
            anon_sent_body = anonymize_text(plain_sent)

            update_composed_draft_sent(
                draft_id=row["id"],
                sent_body=anon_sent_body,
                was_edited=was_edited,
                edit_distance_ratio=edit_distance_ratio,
                chars_added=chars_added,
                chars_removed=chars_removed,
                sent_at=sent_at,
                sent_message_sender=sender,
                sent_message_id=message_id,
                sent_similarity=similarity,
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
