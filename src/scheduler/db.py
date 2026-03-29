"""Database client for user credential storage."""

import json
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
    display_name: str | None = None
    draft_auto_delete_enabled: bool = True


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
) -> tuple[UserRow, bool]:
    """Upsert a user. Returns (user, is_new) where is_new is True for fresh inserts."""
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
            RETURNING *, (xmax = 0) AS is_new
            """,
            (email, google_refresh_token, google_access_token,
             access_token_expires_at, scheduled_calendar_id),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        col_val = dict(zip(cols, row))
        is_new = col_val.pop("is_new", False)
        filtered_cols = [c for c in cols if c != "is_new"]
        filtered_row = [v for c, v in zip(cols, row) if c != "is_new"]
        return _row_to_user(filtered_cols, filtered_row), is_new


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


def get_stuck_onboarding_users() -> list[UserRow]:
    """Return users with Google tokens but onboarding not completed (null, pending, or running)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM users
               WHERE google_refresh_token IS NOT NULL
                 AND (onboarding_status IS NULL OR onboarding_status IN ('pending', 'running'))""",
        )
        cols = [d[0] for d in cur.description]
        return [_row_to_user(cols, row) for row in cur.fetchall()]


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


def update_draft_auto_delete(user_id: str, enabled: bool) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET draft_auto_delete_enabled = %s, updated_at = now() WHERE id = %s",
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


# --- Pending Invites ---


@dataclass
class PendingInviteRow:
    id: str
    user_id: str
    thread_id: str
    attendee_emails: list[str]
    event_summary: str
    event_start: datetime
    event_end: datetime
    add_google_meet: bool
    created_at: datetime
    location: str = ""


def create_pending_invite(
    user_id: str,
    thread_id: str,
    attendee_emails: list[str],
    event_summary: str,
    event_start: datetime,
    event_end: datetime,
    add_google_meet: bool = False,
    location: str = "",
) -> PendingInviteRow:
    """Create or overwrite a pending invite for a thread."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pending_invites (user_id, thread_id, attendee_emails, event_summary,
                                         event_start, event_end, add_google_meet, location)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, thread_id) DO UPDATE SET
                attendee_emails = EXCLUDED.attendee_emails,
                event_summary = EXCLUDED.event_summary,
                event_start = EXCLUDED.event_start,
                event_end = EXCLUDED.event_end,
                add_google_meet = EXCLUDED.add_google_meet,
                location = EXCLUDED.location
            RETURNING *
            """,
            (user_id, thread_id, json.dumps(attendee_emails), event_summary,
             event_start, event_end, add_google_meet, location),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return _pending_invite_from_row(cols, row)


def _pending_invite_from_row(cols, row) -> PendingInviteRow:
    data = dict(zip(cols, row))
    if isinstance(data.get("attendee_emails"), str):
        data["attendee_emails"] = json.loads(data["attendee_emails"])
    return PendingInviteRow(**data)


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
        return _pending_invite_from_row(cols, row)


def update_pending_invite(
    invite_id: str,
    attendee_emails: list[str] | None = None,
    event_summary: str | None = None,
    event_start: datetime | None = None,
    event_end: datetime | None = None,
    add_google_meet: bool | None = None,
    location: str | None = None,
) -> None:
    """Update only the provided fields on a pending invite."""
    sets: list[str] = []
    vals: list = []
    if attendee_emails is not None:
        sets.append("attendee_emails = %s")
        vals.append(json.dumps(attendee_emails))
    if event_summary is not None:
        sets.append("event_summary = %s")
        vals.append(event_summary)
    if event_start is not None:
        sets.append("event_start = %s")
        vals.append(event_start)
    if event_end is not None:
        sets.append("event_end = %s")
        vals.append(event_end)
    if add_google_meet is not None:
        sets.append("add_google_meet = %s")
        vals.append(add_google_meet)
    if location is not None:
        sets.append("location = %s")
        vals.append(location)
    if not sets:
        return
    vals.append(invite_id)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE pending_invites SET {', '.join(sets)} WHERE id = %s", vals)
        conn.commit()


def delete_pending_invite(invite_id: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM pending_invites WHERE id = %s", (invite_id,))
        conn.commit()


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


def insert_page_event(event: str, properties: dict | None = None) -> None:
    """Insert an anonymous page event (no user_id required)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO page_events (event, properties) VALUES (%s, %s)",
            (event, json.dumps(properties or {})),
        )
        conn.commit()


def insert_analytics_event(user_id: str, event: str, properties: dict | None = None) -> None:
    """Insert a row into analytics_events."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO analytics_events (user_id, event, properties) VALUES (%s, %s, %s)",
            (user_id, event, json.dumps(properties or {})),
        )
        conn.commit()


def store_composed_draft(
    user_id: str,
    thread_id: str,
    draft_id: str,
    thread_context: list[dict],
    subject: str,
    body: str,
    was_autopilot: bool = False,
    raw_body: str | None = None,
    refresh_count: int = 0,
    suggested_windows: list[dict] | None = None,
) -> None:
    """Insert a row into composed_drafts with anonymized content."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO composed_drafts
                (user_id, thread_id, draft_id, thread_context, original_subject, original_body,
                 was_autopilot, raw_body, refresh_count, suggested_windows)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, thread_id, draft_id, json.dumps(thread_context), subject, body,
             was_autopilot, raw_body, refresh_count, json.dumps(suggested_windows or [])),
        )
        conn.commit()


def get_composed_draft_by_thread(user_id: str, thread_id: str) -> dict | None:
    """Get the most recent unsent composed draft for a user+thread pair."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM composed_drafts WHERE user_id = %s AND thread_id = %s AND sent_at IS NULL ORDER BY composed_at DESC LIMIT 1",
            (user_id, thread_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))


def update_composed_draft_sent(
    draft_id: str,
    sent_body: str,
    was_edited: bool,
    edit_distance_ratio: float,
    chars_added: int,
    chars_removed: int,
    sent_at,
    sent_message_sender: str | None = None,
    sent_message_id: str | None = None,
    sent_similarity: float | None = None,
) -> None:
    """Update a composed_drafts row with sent-time diff metrics."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE composed_drafts
            SET sent_body = %s, was_edited = %s, edit_distance_ratio = %s,
                chars_added = %s, chars_removed = %s, sent_at = %s,
                sent_message_sender = %s, sent_message_id = %s, sent_similarity = %s
            WHERE id = %s
            """,
            (sent_body, was_edited, edit_distance_ratio, chars_added, chars_removed, sent_at,
             sent_message_sender, sent_message_id, sent_similarity, draft_id),
        )
        conn.commit()


def get_stale_unsent_drafts(hours: int = 48) -> list[dict]:
    """Get unsent composed drafts older than the given hours, for users with auto-delete enabled.

    Excludes drafts still eligible for morning refresh (refresh_count < 3) —
    those are handled by the refresh loop, not the auto-delete.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT cd.id, cd.user_id, cd.draft_id, cd.thread_id, cd.original_subject
            FROM composed_drafts cd
            JOIN users u ON u.id = cd.user_id
            WHERE cd.sent_at IS NULL
              AND cd.composed_at < now() - make_interval(hours => %s)
              AND u.draft_auto_delete_enabled = TRUE
              AND cd.refresh_count >= 3
            """,
            (hours,),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def mark_draft_auto_deleted(draft_id: str) -> None:
    """Mark a composed draft as auto-deleted by setting sent_at (prevents re-processing)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM composed_drafts WHERE id = %s",
            (draft_id,),
        )
        conn.commit()


def get_drafts_eligible_for_refresh(max_refresh_count: int = 3) -> list[dict]:
    """Get unsent drafts whose suggested times are stale (all in the past).

    A draft is eligible for refresh when:
    - It has suggested_windows and ALL of them are in the past, OR
    - It has no suggested_windows (availability mode) and is older than 24 hours
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT cd.id, cd.user_id, cd.draft_id, cd.thread_id, cd.original_subject,
                   cd.refresh_count, cd.raw_body, cd.suggested_windows, cd.composed_at,
                   u.email AS user_email, u.autopilot_enabled, u.calendar_ids
            FROM composed_drafts cd
            JOIN users u ON u.id = cd.user_id
            WHERE cd.sent_at IS NULL
              AND cd.refresh_count < %s
              AND u.draft_auto_delete_enabled = TRUE
              AND u.system_enabled = TRUE
            """,
            (max_refresh_count,),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


_TZ = "America/Los_Angeles"


def get_funnel_data(weeks: int = 12, include_current: bool = False) -> list[dict]:
    """Weekly funnel: page views → signup clicks → signups → onboarded → first draft sent."""
    with _conn() as conn, conn.cursor() as cur:
        end_expr = "date_trunc('week', (now() AT TIME ZONE %s))" if include_current else "date_trunc('week', (now() AT TIME ZONE %s)) - interval '1 week'"
        cur.execute(
            f"""
            WITH week_series AS (
                SELECT generate_series(
                    date_trunc('week', (now() AT TIME ZONE %s) - make_interval(weeks => %s)),
                    {end_expr},
                    '1 week'::interval
                ) AS week
            ),
            page_views AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'landing_page_view'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            signup_clicks AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'signup_click'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            signups AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week, count(*) AS cnt
                FROM users
                WHERE created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            onboarded AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week, count(DISTINCT user_id) AS cnt
                FROM analytics_events
                WHERE event = 'onboarding_completed'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            first_drafts AS (
                SELECT date_trunc('week', min_sent AT TIME ZONE %s) AS week, count(*) AS cnt
                FROM (
                    SELECT user_id, min(created_at) AS min_sent
                    FROM analytics_events
                    WHERE event = 'draft_sent'
                      AND created_at >= now() - make_interval(weeks => %s)
                    GROUP BY user_id
                ) sub
                GROUP BY 1
            )
            SELECT
                ws.week,
                COALESCE(pv.cnt, 0) AS page_views,
                COALESCE(sc.cnt, 0) AS signup_clicks,
                COALESCE(s.cnt, 0) AS signups,
                COALESCE(o.cnt, 0) AS onboarded,
                COALESCE(f.cnt, 0) AS first_draft_sent
            FROM week_series ws
            LEFT JOIN page_views pv ON pv.week = ws.week
            LEFT JOIN signup_clicks sc ON sc.week = ws.week
            LEFT JOIN signups s ON s.week = ws.week
            LEFT JOIN onboarded o ON o.week = ws.week
            LEFT JOIN first_drafts f ON f.week = ws.week
            ORDER BY ws.week
            """,
            (_TZ, weeks, _TZ, _TZ, weeks, _TZ, weeks, _TZ, weeks, _TZ, weeks, _TZ, weeks),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_funnel_data_daily(days: int = 7, include_current: bool = False) -> list[dict]:
    """Daily funnel: page views → signup clicks → signups → onboarded → first draft sent."""
    with _conn() as conn, conn.cursor() as cur:
        end_expr = "date_trunc('day', (now() AT TIME ZONE %s))" if include_current else "date_trunc('day', (now() AT TIME ZONE %s)) - interval '1 day'"
        cur.execute(
            f"""
            WITH day_series AS (
                SELECT generate_series(
                    date_trunc('day', (now() AT TIME ZONE %s) - make_interval(days => %s)),
                    {end_expr},
                    '1 day'::interval
                ) AS day
            ),
            page_views AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'landing_page_view'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            signup_clicks AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'signup_click'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            signups AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day, count(*) AS cnt
                FROM users
                WHERE created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            onboarded AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day, count(DISTINCT user_id) AS cnt
                FROM analytics_events
                WHERE event = 'onboarding_completed'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            first_drafts AS (
                SELECT date_trunc('day', min_sent AT TIME ZONE %s) AS day, count(*) AS cnt
                FROM (
                    SELECT user_id, min(created_at) AS min_sent
                    FROM analytics_events
                    WHERE event = 'draft_sent'
                      AND created_at >= now() - make_interval(days => %s)
                    GROUP BY user_id
                ) sub
                GROUP BY 1
            )
            SELECT
                ds.day AS week,
                COALESCE(pv.cnt, 0) AS page_views,
                COALESCE(sc.cnt, 0) AS signup_clicks,
                COALESCE(s.cnt, 0) AS signups,
                COALESCE(o.cnt, 0) AS onboarded,
                COALESCE(f.cnt, 0) AS first_draft_sent
            FROM day_series ds
            LEFT JOIN page_views pv ON pv.day = ds.day
            LEFT JOIN signup_clicks sc ON sc.day = ds.day
            LEFT JOIN signups s ON s.day = ds.day
            LEFT JOIN onboarded o ON o.day = ds.day
            LEFT JOIN first_drafts f ON f.day = ds.day
            ORDER BY ds.day
            """,
            (_TZ, days, _TZ, _TZ, days, _TZ, days, _TZ, days, _TZ, days, _TZ, days),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_demo_funnel_data(weeks: int = 12, include_current: bool = False) -> list[dict]:
    """Weekly demo funnel: demo views → messages sent → draft sent → complete → booked → CTA signup."""
    with _conn() as conn, conn.cursor() as cur:
        end_expr = "date_trunc('week', (now() AT TIME ZONE %s))" if include_current else "date_trunc('week', (now() AT TIME ZONE %s)) - interval '1 week'"
        cur.execute(
            f"""
            WITH week_series AS (
                SELECT generate_series(
                    date_trunc('week', (now() AT TIME ZONE %s) - make_interval(weeks => %s)),
                    {end_expr},
                    '1 week'::interval
                ) AS week
            ),
            demo_views AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_page_view'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            demo_messages AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_message_sent'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            demo_sends AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_send_clicked'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            demo_complete AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_conversation_complete'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            demo_booked AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_book_clicked'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            demo_cta AS (
                SELECT date_trunc('week', created_at AT TIME ZONE %s) AS week,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_cta_signup_click'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            )
            SELECT
                ws.week,
                COALESCE(dv.cnt, 0) AS demo_views,
                COALESCE(dm.cnt, 0) AS demo_messages,
                COALESCE(ds.cnt, 0) AS demo_sends,
                COALESCE(dc.cnt, 0) AS demo_complete,
                COALESCE(db.cnt, 0) AS demo_booked,
                COALESCE(dt.cnt, 0) AS demo_cta_signups
            FROM week_series ws
            LEFT JOIN demo_views dv ON dv.week = ws.week
            LEFT JOIN demo_messages dm ON dm.week = ws.week
            LEFT JOIN demo_sends ds ON ds.week = ws.week
            LEFT JOIN demo_complete dc ON dc.week = ws.week
            LEFT JOIN demo_booked db ON db.week = ws.week
            LEFT JOIN demo_cta dt ON dt.week = ws.week
            ORDER BY ws.week
            """,
            (_TZ, weeks, _TZ, _TZ, weeks, _TZ, weeks, _TZ, weeks, _TZ, weeks, _TZ, weeks, _TZ, weeks),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_demo_funnel_data_daily(days: int = 7, include_current: bool = False) -> list[dict]:
    """Daily demo funnel: demo views → messages sent → draft sent → complete → booked → CTA signup."""
    with _conn() as conn, conn.cursor() as cur:
        end_expr = "date_trunc('day', (now() AT TIME ZONE %s))" if include_current else "date_trunc('day', (now() AT TIME ZONE %s)) - interval '1 day'"
        cur.execute(
            f"""
            WITH day_series AS (
                SELECT generate_series(
                    date_trunc('day', (now() AT TIME ZONE %s) - make_interval(days => %s)),
                    {end_expr},
                    '1 day'::interval
                ) AS day
            ),
            demo_views AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_page_view'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            demo_messages AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_message_sent'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            demo_sends AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_send_clicked'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            demo_complete AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_conversation_complete'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            demo_booked AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_book_clicked'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            ),
            demo_cta AS (
                SELECT date_trunc('day', created_at AT TIME ZONE %s) AS day,
                       count(DISTINCT properties->>'session_id') FILTER (WHERE properties->>'session_id' IS NOT NULL)
                       + count(*) FILTER (WHERE properties->>'session_id' IS NULL) AS cnt
                FROM page_events
                WHERE event = 'demo_cta_signup_click'
                  AND created_at >= now() - make_interval(days => %s)
                GROUP BY 1
            )
            SELECT
                ds.day AS week,
                COALESCE(dv.cnt, 0) AS demo_views,
                COALESCE(dm.cnt, 0) AS demo_messages,
                COALESCE(ds2.cnt, 0) AS demo_sends,
                COALESCE(dc.cnt, 0) AS demo_complete,
                COALESCE(db.cnt, 0) AS demo_booked,
                COALESCE(dt.cnt, 0) AS demo_cta_signups
            FROM day_series ds
            LEFT JOIN demo_views dv ON dv.day = ds.day
            LEFT JOIN demo_messages dm ON dm.day = ds.day
            LEFT JOIN demo_sends ds2 ON ds2.day = ds.day
            LEFT JOIN demo_complete dc ON dc.day = ds.day
            LEFT JOIN demo_booked db ON db.day = ds.day
            LEFT JOIN demo_cta dt ON dt.day = ds.day
            ORDER BY ds.day
            """,
            (_TZ, days, _TZ, _TZ, days, _TZ, days, _TZ, days, _TZ, days, _TZ, days, _TZ, days),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


_ALL_EVENTS = ('user_created', 'onboarding_completed', 'draft_composed', 'draft_sent', 'setting_changed')
_EMAIL_EVENTS = ('draft_sent',)
_RETENTION_EVENTS = ('user_created', 'onboarding_completed')


def get_cohort_data(weeks: int = 8, emails_only: bool = False, include_current: bool = False) -> dict:
    """Rich cohort data: retention by week offset, plus absolute-date series for emails/active/actions."""
    from datetime import timedelta
    action_events = _EMAIL_EVENTS if emails_only else _ALL_EVENTS
    # Always include signup/onboarding so users show as retained from W0
    all_events = list(set(action_events) | set(_RETENTION_EVENTS))
    cutoff_clause = "" if include_current else "AND date_trunc('week', ae.created_at AT TIME ZONE %s) < date_trunc('week', now() AT TIME ZONE %s)"
    tz_params = () if include_current else (_TZ, _TZ)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            WITH cohorts AS (
                SELECT id AS user_id, date_trunc('week', created_at AT TIME ZONE %s) AS cohort_week
                FROM users
                WHERE created_at >= now() - make_interval(weeks => %s)
            ),
            cohort_sizes AS (
                SELECT cohort_week, count(*) AS size
                FROM cohorts
                GROUP BY cohort_week
            ),
            weekly_activity AS (
                SELECT
                    c.cohort_week,
                    date_trunc('week', ae.created_at AT TIME ZONE %s) AS activity_week,
                    FLOOR(EXTRACT(EPOCH FROM date_trunc('week', ae.created_at AT TIME ZONE %s) - c.cohort_week) / 604800)::int AS week_offset,
                    count(DISTINCT c.user_id) AS active_users,
                    count(*) FILTER (WHERE ae.event = 'draft_sent') AS emails_sent,
                    count(*) FILTER (WHERE ae.event = ANY(%s)) AS total_actions
                FROM cohorts c
                JOIN analytics_events ae ON ae.user_id = c.user_id
                WHERE ae.event = ANY(%s)
                  {cutoff_clause}
                GROUP BY c.cohort_week, activity_week, week_offset
            )
            SELECT
                cs.cohort_week,
                cs.size,
                wa.activity_week,
                wa.week_offset,
                COALESCE(wa.active_users, 0) AS active_users,
                COALESCE(wa.emails_sent, 0) AS emails_sent,
                COALESCE(wa.total_actions, 0) AS total_actions
            FROM cohort_sizes cs
            LEFT JOIN weekly_activity wa ON wa.cohort_week = cs.cohort_week
            ORDER BY cs.cohort_week, wa.activity_week
            """,
            (_TZ, weeks, _TZ, _TZ, list(action_events), all_events) + tz_params,
        )
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Current week boundary in Pacific time
        cur.execute("SELECT date_trunc('week', now() AT TIME ZONE %s)", (_TZ,))
        current_week_start = cur.fetchone()[0]
        if hasattr(current_week_start, 'isoformat'):
            current_week_iso = current_week_start.isoformat()
        else:
            current_week_iso = str(current_week_start)

        # Build per-cohort data
        cohort_map: dict[str, dict] = {}
        all_activity_weeks: set[str] = set()
        for row in rows:
            key = row["cohort_week"].isoformat() if hasattr(row["cohort_week"], "isoformat") else str(row["cohort_week"])
            if key not in cohort_map:
                cohort_map[key] = {
                    "week": key,
                    "size": row["size"],
                    "by_offset": {},
                    "by_date": {},
                }
            if row["week_offset"] is not None and row["week_offset"] >= 0:
                cohort_map[key]["by_offset"][row["week_offset"]] = {
                    "active_users": row["active_users"],
                    "emails_sent": row["emails_sent"],
                    "total_actions": row["total_actions"],
                }
            if row["activity_week"] is not None:
                aw_key = row["activity_week"].isoformat()
                all_activity_weeks.add(aw_key)
                cohort_map[key]["by_date"][aw_key] = {
                    "active_users": row["active_users"],
                    "emails_sent": row["emails_sent"],
                    "total_actions": row["total_actions"],
                }

        cohorts = sorted(cohort_map.values(), key=lambda c: c["week"])
        # Max offset = age of the oldest cohort in completed weeks
        if cohorts:
            oldest = datetime.fromisoformat(cohorts[0]["week"])
            max_offset = max(0, int((current_week_start - oldest).total_seconds() / 604800) - (0 if include_current else 1))
        else:
            max_offset = 0
        # Generate full week series from earliest cohort to last boundary
        if cohorts:
            earliest = min(datetime.fromisoformat(c["week"]) for c in cohorts)
            last_week = current_week_start if include_current else current_week_start - timedelta(weeks=1)
            week_cursor = earliest
            while week_cursor <= last_week:
                all_activity_weeks.add(week_cursor.isoformat())
                week_cursor += timedelta(weeks=1)
        sorted_activity_weeks = sorted(all_activity_weeks)

        # Compute max completed offset per cohort
        # When include_current, allow the current incomplete offset too
        def max_completed_offset(cohort_week_iso: str) -> int:
            cohort_start = datetime.fromisoformat(cohort_week_iso)
            delta = current_week_start - cohort_start
            full_weeks = int(delta.total_seconds() / 604800)
            return max(0, full_weeks if include_current else full_weeks - 1)

        # Build retention arrays — use None for offsets beyond what the cohort has completed
        result_cohorts = []
        for c in cohorts:
            size = c["size"]
            max_complete = max_completed_offset(c["week"])
            retention: list[float | None] = []
            for i in range(int(max_offset) + 1):
                if i == 0:
                    retention.append(100.0)
                elif i > max_complete:
                    retention.append(None)
                else:
                    w = c["by_offset"].get(i, {})
                    active = w.get("active_users", 0)
                    retention.append(round(active / size * 100, 1) if size > 0 else 0)

            lifetime_actions: list[float | None] = []
            cumulative = 0
            for i in range(int(max_offset) + 1):
                if i > max_complete:
                    lifetime_actions.append(None)
                else:
                    cumulative += c["by_offset"].get(i, {}).get("total_actions", 0)
                    lifetime_actions.append(round(cumulative / size, 1) if size > 0 else 0)

            result_cohorts.append({
                "week": c["week"],
                "size": size,
                "retention": retention,
                "lifetime_actions": lifetime_actions,
            })

        # Build absolute-date series for emails_sent and active_users
        emails_by_week: list[dict] = []
        active_by_week: list[dict] = []
        for aw in sorted_activity_weeks:
            email_point: dict = {"week": aw}
            active_point: dict = {"week": aw}
            for c in cohorts:
                label = c["week"]
                d = c["by_date"].get(aw, {})
                email_point[label] = d.get("total_actions", 0)
                active_point[label] = d.get("active_users", 0)
            emails_by_week.append(email_point)
            active_by_week.append(active_point)

        return {
            "cohorts": result_cohorts,
            "max_weeks": int(max_offset) + 1,
            "emails_by_week": emails_by_week,
            "active_by_week": active_by_week,
        }


def get_cohort_data_daily(days: int = 7, emails_only: bool = False, include_current: bool = False) -> dict:
    """Same as get_cohort_data but cohorts are grouped by day and activity is daily."""
    from datetime import timedelta
    action_events = _EMAIL_EVENTS if emails_only else _ALL_EVENTS
    all_events = list(set(action_events) | set(_RETENTION_EVENTS))
    cutoff_clause = "" if include_current else "AND date_trunc('day', ae.created_at AT TIME ZONE %s) < date_trunc('day', now() AT TIME ZONE %s)"
    tz_params = () if include_current else (_TZ, _TZ)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            WITH cohorts AS (
                SELECT id AS user_id, date_trunc('day', created_at AT TIME ZONE %s) AS cohort_day
                FROM users
                WHERE created_at >= now() - make_interval(days => %s)
            ),
            cohort_sizes AS (
                SELECT cohort_day, count(*) AS size
                FROM cohorts
                GROUP BY cohort_day
            ),
            daily_activity AS (
                SELECT
                    c.cohort_day,
                    date_trunc('day', ae.created_at AT TIME ZONE %s) AS activity_day,
                    (date_trunc('day', ae.created_at AT TIME ZONE %s)::date - c.cohort_day::date)::int AS day_offset,
                    count(DISTINCT c.user_id) AS active_users,
                    count(*) FILTER (WHERE ae.event = 'draft_sent') AS emails_sent,
                    count(*) FILTER (WHERE ae.event = ANY(%s)) AS total_actions
                FROM cohorts c
                JOIN analytics_events ae ON ae.user_id = c.user_id
                WHERE ae.event = ANY(%s)
                  {cutoff_clause}
                GROUP BY c.cohort_day, activity_day, day_offset
            )
            SELECT
                cs.cohort_day,
                cs.size,
                da.activity_day,
                da.day_offset,
                COALESCE(da.active_users, 0) AS active_users,
                COALESCE(da.emails_sent, 0) AS emails_sent,
                COALESCE(da.total_actions, 0) AS total_actions
            FROM cohort_sizes cs
            LEFT JOIN daily_activity da ON da.cohort_day = cs.cohort_day
            ORDER BY cs.cohort_day, da.activity_day
            """,
            (_TZ, days, _TZ, _TZ, list(action_events), all_events) + tz_params,
        )
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Current day boundary in Pacific time
        cur.execute("SELECT date_trunc('day', now() AT TIME ZONE %s)", (_TZ,))
        current_day_start = cur.fetchone()[0]

        cohort_map: dict[str, dict] = {}
        all_activity_days: set[str] = set()
        for row in rows:
            key = row["cohort_day"].isoformat() if hasattr(row["cohort_day"], "isoformat") else str(row["cohort_day"])
            if key not in cohort_map:
                cohort_map[key] = {
                    "day": key,
                    "size": row["size"],
                    "by_offset": {},
                    "by_date": {},
                }
            if row["day_offset"] is not None and row["day_offset"] >= 0:
                cohort_map[key]["by_offset"][row["day_offset"]] = {
                    "active_users": row["active_users"],
                    "emails_sent": row["emails_sent"],
                    "total_actions": row["total_actions"],
                }
            if row["activity_day"] is not None:
                ad_key = row["activity_day"].isoformat()
                all_activity_days.add(ad_key)
                cohort_map[key]["by_date"][ad_key] = {
                    "active_users": row["active_users"],
                    "emails_sent": row["emails_sent"],
                    "total_actions": row["total_actions"],
                }

        cohorts = sorted(cohort_map.values(), key=lambda c: c["day"])

        # Fill in all days up to last boundary
        if cohorts:
            earliest = min(datetime.fromisoformat(c["day"]) for c in cohorts)
            last_day = current_day_start if include_current else current_day_start - timedelta(days=1)
            cursor = earliest
            while cursor <= last_day:
                all_activity_days.add(cursor.isoformat())
                cursor += timedelta(days=1)
        sorted_activity_days = sorted(all_activity_days)

        if cohorts:
            oldest = datetime.fromisoformat(cohorts[0]["day"])
            max_offset = max(0, (current_day_start - oldest).days - (0 if include_current else 1))
        else:
            max_offset = 0

        def max_completed_offset(cohort_day_iso: str) -> int:
            cohort_start = datetime.fromisoformat(cohort_day_iso)
            delta = current_day_start - cohort_start
            return max(0, delta.days if include_current else delta.days - 1)

        result_cohorts = []
        for c in cohorts:
            size = c["size"]
            max_complete = max_completed_offset(c["day"])
            retention: list[float | None] = []
            for i in range(int(max_offset) + 1):
                if i == 0:
                    retention.append(100.0)
                elif i > max_complete:
                    retention.append(None)
                else:
                    w = c["by_offset"].get(i, {})
                    active = w.get("active_users", 0)
                    retention.append(round(active / size * 100, 1) if size > 0 else 0)
            lifetime_actions: list[float | None] = []
            cumulative = 0
            for i in range(int(max_offset) + 1):
                if i > max_complete:
                    lifetime_actions.append(None)
                else:
                    cumulative += c["by_offset"].get(i, {}).get("total_actions", 0)
                    lifetime_actions.append(round(cumulative / size, 1) if size > 0 else 0)
            result_cohorts.append({
                "week": c["day"],  # keep "week" key for frontend compatibility
                "size": size,
                "retention": retention,
                "lifetime_actions": lifetime_actions,
            })

        emails_by_day: list[dict] = []
        active_by_day: list[dict] = []
        for ad in sorted_activity_days:
            email_point: dict = {"week": ad}
            active_point: dict = {"week": ad}
            for c in cohorts:
                label = c["day"]
                d = c["by_date"].get(ad, {})
                email_point[label] = d.get("total_actions", 0)
                active_point[label] = d.get("active_users", 0)
            emails_by_day.append(email_point)
            active_by_day.append(active_point)

        return {
            "cohorts": result_cohorts,
            "max_weeks": int(max_offset) + 1,
            "emails_by_week": emails_by_day,
            "active_by_week": active_by_day,
        }


def get_draft_stats() -> dict:
    """Aggregate stats for the drafts tab."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT
                count(*) AS total_drafts,
                count(*) FILTER (WHERE sent_at IS NOT NULL) AS total_sent,
                count(*) FILTER (WHERE was_edited = TRUE) AS total_edited,
                round(avg(edit_distance_ratio) FILTER (WHERE sent_at IS NOT NULL)::numeric, 4) AS avg_edit_pct,
                round(avg(chars_added) FILTER (WHERE sent_at IS NOT NULL)::numeric, 1) AS avg_chars_added,
                round(avg(chars_removed) FILTER (WHERE sent_at IS NOT NULL)::numeric, 1) AS avg_chars_removed,
                count(*) FILTER (WHERE was_autopilot = TRUE) AS total_autopilot,
                count(*) FILTER (WHERE was_autopilot = TRUE AND sent_at IS NOT NULL) AS autopilot_sent
            FROM composed_drafts
        """)
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        result = dict(zip(cols, row))
        # Convert Decimal to float for JSON
        for k, v in result.items():
            if v is not None and not isinstance(v, (int, float, str)):
                result[k] = float(v)
        return result


def get_admin_drafts(
    page: int = 1,
    per_page: int = 20,
    email_search: str | None = None,
    edited_only: bool = False,
    autopilot_only: bool = False,
) -> tuple[list[dict], int]:
    """Paginated composed_drafts with user email, for admin browsing."""
    conditions = []
    params: list = []

    if email_search:
        conditions.append("u.email ILIKE %s")
        params.append(f"%{email_search}%")
    if edited_only:
        conditions.append("cd.was_edited = TRUE")
    if autopilot_only:
        conditions.append("cd.was_autopilot = TRUE")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT count(*) FROM composed_drafts cd JOIN users u ON u.id = cd.user_id {where_clause}",
            params,
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT cd.id, u.email AS user_email, cd.original_subject, cd.original_body,
                   cd.sent_body, cd.was_edited, cd.edit_distance_ratio,
                   cd.chars_added, cd.chars_removed, cd.was_autopilot,
                   cd.composed_at, cd.sent_at, cd.thread_context,
                   cd.sent_message_sender, cd.sent_message_id, cd.sent_similarity
            FROM composed_drafts cd
            JOIN users u ON u.id = cd.user_id
            {where_clause}
            ORDER BY cd.composed_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, (page - 1) * per_page],
        )
        cols = [desc[0] for desc in cur.description]
        drafts = [dict(zip(cols, row)) for row in cur.fetchall()]
        return drafts, total


def update_display_name(user_id: str, display_name: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET display_name = %s, updated_at = now() WHERE id = %s",
            (display_name, user_id),
        )
        conn.commit()


# --- Scheduling Links ---


@dataclass
class SchedulingLinkRow:
    id: str
    user_id: str
    thread_id: str | None
    mode: str
    attendee_email: str
    attendee_name: str | None
    event_summary: str
    duration_minutes: int
    timezone: str
    suggested_windows: list[dict]
    recipient_availability: list[dict] | None
    recipient_submitted_at: datetime | None
    confirmed_time_start: datetime | None
    confirmed_time_end: datetime | None
    confirmed_at: datetime | None
    calendar_event_id: str | None
    status: str
    add_google_meet: bool
    location: str
    expires_at: datetime
    created_at: datetime


def _scheduling_link_from_row(cols, row) -> SchedulingLinkRow:
    data = dict(zip(cols, row))
    for field in ("suggested_windows", "recipient_availability"):
        val = data.get(field)
        if isinstance(val, str):
            data[field] = json.loads(val)
    return SchedulingLinkRow(**data)


def create_scheduling_link(
    user_id: str,
    attendee_email: str,
    mode: str = "availability",
    event_summary: str = "Meeting",
    duration_minutes: int = 30,
    tz: str = "America/New_York",
    suggested_windows: list[dict] | None = None,
    thread_id: str | None = None,
    attendee_name: str | None = None,
    add_google_meet: bool = False,
    location: str = "",
) -> SchedulingLinkRow:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scheduling_links
                (user_id, thread_id, mode, attendee_email, attendee_name,
                 event_summary, duration_minutes, timezone, suggested_windows,
                 add_google_meet, location)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, thread_id, mode, attendee_email, attendee_name,
             event_summary, duration_minutes, tz,
             json.dumps(suggested_windows or []),
             add_google_meet, location),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        conn.commit()
        return _scheduling_link_from_row(cols, row)


def get_scheduling_link(link_id: str) -> SchedulingLinkRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM scheduling_links WHERE id = %s", (link_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return _scheduling_link_from_row(cols, row)


def submit_recipient_availability(
    link_id: str,
    availability: list[dict],
    submitted_at: datetime | None = None,
) -> None:
    if submitted_at is None:
        submitted_at = datetime.now(timezone.utc)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scheduling_links
            SET recipient_availability = %s, recipient_submitted_at = %s, status = 'submitted'
            WHERE id = %s
            """,
            (json.dumps(availability), submitted_at, link_id),
        )
        conn.commit()


def confirm_scheduling_link(
    link_id: str,
    start: datetime,
    end: datetime,
    calendar_event_id: str,
) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scheduling_links
            SET confirmed_time_start = %s, confirmed_time_end = %s,
                confirmed_at = now(), calendar_event_id = %s, status = 'confirmed'
            WHERE id = %s AND status IN ('pending', 'submitted')
            """,
            (start, end, calendar_event_id, link_id),
        )
        conn.commit()


def cleanup_expired_scheduling_links() -> int:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE scheduling_links SET status = 'expired' WHERE status = 'pending' AND expires_at < now()"
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
                scheduled_calendar_id = NULL,
                onboarding_status = NULL,
                updated_at = now()
            WHERE id = %s
            """,
            (user_id,),
        )
        conn.commit()
