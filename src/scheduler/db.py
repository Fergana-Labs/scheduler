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


def update_stash_calendar_id(user_id: str, stash_calendar_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET stash_calendar_id = %s, updated_at = now() WHERE id = %s",
            (stash_calendar_id, user_id),
        )
        conn.commit()
