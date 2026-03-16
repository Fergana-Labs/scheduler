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
    google_refresh_token: str
    google_access_token: str | None
    access_token_expires_at: datetime | None
    stash_calendar_id: str | None
    gmail_history_id: str | None
    created_at: datetime
    updated_at: datetime


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


def get_all_user_ids() -> list[str]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users")
        return [str(row[0]) for row in cur.fetchall()]


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
