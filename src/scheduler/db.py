"""Database client for user credential storage."""

from datetime import datetime, timezone
from dataclasses import dataclass, fields

import psycopg2
import psycopg2.extras

from scheduler.config import config

psycopg2.extras.register_uuid()

_USER_ROW_FIELDS: set[str] = set()  # populated after class definition


def _row_to_user(cols, row) -> "UserRow":
    """Build a UserRow, ignoring any DB columns not yet on the dataclass.

    This prevents 500s during deployment rollover when a migration adds a
    column before the old instance is replaced.
    """
    data = {k: v for k, v in zip(cols, row) if k in _USER_ROW_FIELDS}
    return UserRow(**data)


@dataclass
class UserRow:
    id: str
    email: str
    google_refresh_token: str | None
    google_access_token: str | None
    access_token_expires_at: datetime | None
    scheduled_calendar_id: str | None
    gmail_history_id: str | None
    system_enabled: bool
    scheduled_branding_enabled: bool
    autopilot_enabled: bool
    process_sales_emails: bool
    created_at: datetime
    updated_at: datetime
    reasoning_emails_enabled: bool = False
    auth0_sub: str | None = None
    calendar_ids: list[str] | None = None
    onboarding_status: str | None = None
    matrix_homeserver_url: str | None = None
    matrix_access_token: str | None = None
    matrix_user_id: str | None = None
    matrix_sync_enabled: bool = False


_USER_ROW_FIELDS.update(f.name for f in fields(UserRow))


def _conn():
    return psycopg2.connect(config.database_url)


def get_user_by_email(email: str) -> UserRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return _row_to_user(cols, row)


def get_user_by_id(user_id: str) -> UserRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return _row_to_user(cols, row)


def upsert_user(
    email: str,
    google_refresh_token: str,
    google_access_token: str | None = None,
    access_token_expires_at: datetime | None = None,
    scheduled_calendar_id: str | None = None,
) -> UserRow:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (email, google_refresh_token, google_access_token,
                               access_token_expires_at, scheduled_calendar_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                google_refresh_token = EXCLUDED.google_refresh_token,
                google_access_token = EXCLUDED.google_access_token,
                access_token_expires_at = EXCLUDED.access_token_expires_at,
                scheduled_calendar_id = COALESCE(EXCLUDED.scheduled_calendar_id, users.scheduled_calendar_id),
                updated_at = now()
            RETURNING *
            """,
            (email, google_refresh_token, google_access_token,
             access_token_expires_at, scheduled_calendar_id),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return _row_to_user(cols, row)


def update_user_tokens(
    user_id: str,
    google_access_token: str,
    access_token_expires_at: datetime | None = None,
) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE users SET google_access_token = %s, access_token_expires_at = %s,
                             updated_at = now()
            WHERE id = %s
            """,
            (google_access_token, access_token_expires_at, user_id),
        )
        conn.commit()


def update_gmail_history_id(user_id: str, history_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET gmail_history_id = %s, updated_at = now() WHERE id = %s",
            (history_id, user_id),
        )
        conn.commit()


def get_user_by_auth0_sub(auth0_sub: str) -> UserRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE auth0_sub = %s", (auth0_sub,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return _row_to_user(cols, row)


def create_user_from_auth0(email: str, auth0_sub: str) -> UserRow:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (email, auth0_sub)
            VALUES (%s, %s)
            RETURNING *
            """,
            (email, auth0_sub),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return _row_to_user(cols, row)


def set_auth0_sub(user_id: str, auth0_sub: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET auth0_sub = %s, updated_at = now() WHERE id = %s",
            (auth0_sub, user_id),
        )
        conn.commit()


def update_google_tokens(
    user_id: str,
    google_refresh_token: str,
    google_access_token: str | None = None,
    access_token_expires_at: datetime | None = None,
) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE users SET
                google_refresh_token = %s,
                google_access_token = %s,
                access_token_expires_at = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (google_refresh_token, google_access_token, access_token_expires_at, user_id),
        )
        conn.commit()


def get_all_user_ids() -> list[str]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users")
        return [str(row[0]) for row in cur.fetchall()]


def update_scheduled_branding(user_id: str, enabled: bool) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET scheduled_branding_enabled = %s, updated_at = now() WHERE id = %s",
            (enabled, user_id),
        )
        conn.commit()


def update_system_enabled(user_id: str, enabled: bool) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET system_enabled = %s, updated_at = now() WHERE id = %s",
            (enabled, user_id),
        )
        conn.commit()


def update_autopilot(user_id: str, enabled: bool) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET autopilot_enabled = %s, updated_at = now() WHERE id = %s",
            (enabled, user_id),
        )
        conn.commit()


def update_process_sales_emails(user_id: str, enabled: bool) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET process_sales_emails = %s, updated_at = now() WHERE id = %s",
            (enabled, user_id),
        )
        conn.commit()


def update_reasoning_emails_enabled(user_id: str, enabled: bool) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET reasoning_emails_enabled = %s, updated_at = now() WHERE id = %s",
            (enabled, user_id),
        )
        conn.commit()


def update_scheduled_calendar_id(user_id: str, scheduled_calendar_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET scheduled_calendar_id = %s, updated_at = now() WHERE id = %s",
            (scheduled_calendar_id, user_id),
        )
        conn.commit()


# --- Guides ---


@dataclass
class GuideRow:
    id: str
    user_id: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime


def upsert_guide(user_id: str, name: str, content: str) -> GuideRow:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO guides (user_id, name, content)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, name) DO UPDATE SET
                content = EXCLUDED.content,
                updated_at = now()
            RETURNING *
            """,
            (user_id, name, content),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return GuideRow(**dict(zip(cols, row)))


def get_guide(user_id: str, name: str) -> GuideRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM guides WHERE user_id = %s AND name = %s",
            (user_id, name),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return GuideRow(**dict(zip(cols, row)))


def get_guides_for_user(user_id: str) -> list[GuideRow]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM guides WHERE user_id = %s ORDER BY name",
            (user_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return []
        cols = [desc[0] for desc in cur.description]
        return [GuideRow(**dict(zip(cols, row))) for row in rows]


def delete_user(user_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM guides WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()


def try_claim_message(user_id: str, message_id: str) -> bool:
    """Atomically claim a message for processing. Returns True if claimed, False if already claimed.

    This replaces the old check-then-mark pattern to prevent duplicate processing
    from concurrent webhook handlers.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO processed_messages (user_id, message_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, message_id) DO NOTHING
            RETURNING 1
            """,
            (user_id, message_id),
        )
        claimed = cur.fetchone() is not None
        conn.commit()
        return claimed


def cleanup_processed_messages(days: int = 7) -> int:
    """Delete processed message records older than the given number of days."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM processed_messages WHERE processed_at < now() - make_interval(days => %s)",
            (days,),
        )
        count = cur.rowcount
        conn.commit()
        return count


def update_calendar_ids(user_id: str, calendar_ids: list[str]) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET calendar_ids = %s, updated_at = now() WHERE id = %s",
            (calendar_ids, user_id),
        )
        conn.commit()


def update_onboarding_status(user_id: str, status: str | None) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET onboarding_status = %s, updated_at = now() WHERE id = %s",
            (status, user_id),
        )
        conn.commit()


def disconnect_user(user_id: str) -> None:
    """Revoke Google tokens and delete guides, but keep the user row."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM guides WHERE user_id = %s", (user_id,))
        cur.execute(
            """
            UPDATE users SET
                google_refresh_token = NULL,
                google_access_token = NULL,
                access_token_expires_at = NULL,
                gmail_history_id = NULL,
                scheduled_calendar_id = NULL,
                onboarding_status = NULL,
                updated_at = now()
            WHERE id = %s
            """,
            (user_id,),
        )
        conn.commit()


# --- Pending Replies (Chat) ---


@dataclass
class PendingReplyRow:
    id: str
    user_id: str
    platform: str
    room_id: str
    sender_name: str
    conversation_context: list | dict | None
    proposed_reply: str
    status: str
    created_at: datetime
    updated_at: datetime


def create_pending_reply(
    user_id: str,
    platform: str,
    room_id: str,
    sender_name: str,
    proposed_reply: str,
    conversation_context: list | dict | None = None,
) -> PendingReplyRow:
    """Create a new pending reply for user review."""
    import json as _json

    context_json = _json.dumps(conversation_context) if conversation_context else None

    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pending_replies
                (user_id, platform, room_id, sender_name, conversation_context, proposed_reply)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, platform, room_id, sender_name, context_json, proposed_reply),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return PendingReplyRow(**dict(zip(cols, row)))


def get_pending_replies(user_id: str, status: str = "pending") -> list[PendingReplyRow]:
    """Get all pending replies for a user, filtered by status."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM pending_replies WHERE user_id = %s AND status = %s ORDER BY created_at DESC",
            (user_id, status),
        )
        rows = cur.fetchall()
        if not rows:
            return []
        cols = [desc[0] for desc in cur.description]
        return [PendingReplyRow(**dict(zip(cols, row))) for row in rows]


def get_pending_reply_by_id(reply_id: str) -> PendingReplyRow | None:
    """Get a single pending reply by ID."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM pending_replies WHERE id = %s", (reply_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return PendingReplyRow(**dict(zip(cols, row)))


def approve_pending_reply(reply_id: str) -> PendingReplyRow | None:
    """Mark a pending reply as approved."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pending_replies SET status = 'approved', updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (reply_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return PendingReplyRow(**dict(zip(cols, row)))


def dismiss_pending_reply(reply_id: str) -> PendingReplyRow | None:
    """Mark a pending reply as dismissed."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pending_replies SET status = 'dismissed', updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (reply_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return PendingReplyRow(**dict(zip(cols, row)))


def update_pending_reply(reply_id: str, new_text: str) -> PendingReplyRow | None:
    """Update the proposed reply text of a pending reply."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pending_replies SET proposed_reply = %s, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (new_text, reply_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return PendingReplyRow(**dict(zip(cols, row)))
