"""Database client for user credential storage."""

from datetime import datetime, timezone
from dataclasses import dataclass

import psycopg2
import psycopg2.extras

from scheduler.config import config

psycopg2.extras.register_uuid()


@dataclass
class UserRow:
    id: str
    email: str
    google_refresh_token: str | None
    google_access_token: str | None
    access_token_expires_at: datetime | None
    stash_calendar_id: str | None
    gmail_history_id: str | None
    system_enabled: bool
    stash_branding_enabled: bool
    autopilot_enabled: bool
    process_sales_emails: bool
    reasoning_emails_enabled: bool
    created_at: datetime
    updated_at: datetime
    auth0_sub: str | None = None
    reasoning_emails_enabled: bool = False


def _conn():
    return psycopg2.connect(config.database_url)


def get_user_by_email(email: str) -> UserRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return UserRow(**dict(zip(cols, row)))


def get_user_by_id(user_id: str) -> UserRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return UserRow(**dict(zip(cols, row)))


def upsert_user(
    email: str,
    google_refresh_token: str,
    google_access_token: str | None = None,
    access_token_expires_at: datetime | None = None,
    stash_calendar_id: str | None = None,
) -> UserRow:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (email, google_refresh_token, google_access_token,
                               access_token_expires_at, stash_calendar_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                google_refresh_token = EXCLUDED.google_refresh_token,
                google_access_token = EXCLUDED.google_access_token,
                access_token_expires_at = EXCLUDED.access_token_expires_at,
                stash_calendar_id = COALESCE(EXCLUDED.stash_calendar_id, users.stash_calendar_id),
                updated_at = now()
            RETURNING *
            """,
            (email, google_refresh_token, google_access_token,
             access_token_expires_at, stash_calendar_id),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return UserRow(**dict(zip(cols, row)))


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
        return UserRow(**dict(zip(cols, row)))


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
        return UserRow(**dict(zip(cols, row)))


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


def update_stash_branding(user_id: str, enabled: bool) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET stash_branding_enabled = %s, updated_at = now() WHERE id = %s",
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


def update_stash_calendar_id(user_id: str, stash_calendar_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET stash_calendar_id = %s, updated_at = now() WHERE id = %s",
            (stash_calendar_id, user_id),
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


# --- Pending Invites ---


@dataclass
class PendingInviteRow:
    id: str
    user_id: str
    thread_id: str
    attendee_email: str
    event_summary: str
    event_start: datetime
    event_end: datetime
    created_at: datetime
    add_google_meet: bool = False


def create_pending_invite(
    user_id: str,
    thread_id: str,
    attendee_email: str,
    event_summary: str,
    event_start: datetime,
    event_end: datetime,
    add_google_meet: bool = False,
) -> PendingInviteRow:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pending_invites (user_id, thread_id, attendee_email,
                                         event_summary, event_start, event_end,
                                         add_google_meet)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, thread_id) DO UPDATE SET
                attendee_email = EXCLUDED.attendee_email,
                event_summary = EXCLUDED.event_summary,
                event_start = EXCLUDED.event_start,
                event_end = EXCLUDED.event_end,
                add_google_meet = EXCLUDED.add_google_meet
            RETURNING *
            """,
            (user_id, thread_id, attendee_email, event_summary, event_start, event_end, add_google_meet),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return PendingInviteRow(**dict(zip(cols, row)))


def get_pending_invite_by_thread(user_id: str, thread_id: str) -> PendingInviteRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM pending_invites WHERE user_id = %s AND thread_id = %s",
            (user_id, thread_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return PendingInviteRow(**dict(zip(cols, row)))


def delete_pending_invite(invite_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pending_invites WHERE id = %s", (invite_id,))
        conn.commit()


def delete_user(user_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM guides WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()


def is_message_processed(user_id: str, message_id: str) -> bool:
    """Check if a message has already been processed (without marking it)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM processed_messages WHERE user_id = %s AND message_id = %s",
            (user_id, message_id),
        )
        return cur.fetchone() is not None


def mark_message_processed(user_id: str, message_id: str) -> None:
    """Mark a message as processed."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO processed_messages (user_id, message_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, message_id) DO NOTHING
            """,
            (user_id, message_id),
        )
        conn.commit()


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
                stash_calendar_id = NULL,
                updated_at = now()
            WHERE id = %s
            """,
            (user_id,),
        )
        conn.commit()
