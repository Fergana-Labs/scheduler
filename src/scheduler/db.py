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
) -> None:
    """Insert a row into composed_drafts with anonymized content."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO composed_drafts
                (user_id, thread_id, draft_id, thread_context, original_subject, original_body, was_autopilot)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, thread_id, draft_id, json.dumps(thread_context), subject, body, was_autopilot),
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
) -> None:
    """Update a composed_drafts row with sent-time diff metrics."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE composed_drafts
            SET sent_body = %s, was_edited = %s, edit_distance_ratio = %s,
                chars_added = %s, chars_removed = %s, sent_at = %s
            WHERE id = %s
            """,
            (sent_body, was_edited, edit_distance_ratio, chars_added, chars_removed, sent_at, draft_id),
        )
        conn.commit()


def cleanup_old_analytics(days: int = 90) -> int:
    """Delete analytics_events older than the given number of days."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM analytics_events WHERE created_at < now() - make_interval(days => %s)",
            (days,),
        )
        count = cur.rowcount
        conn.commit()
        return count


def cleanup_composed_drafts(days: int = 90) -> int:
    """Delete composed_drafts older than the given number of days."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM composed_drafts WHERE composed_at < now() - make_interval(days => %s)",
            (days,),
        )
        count = cur.rowcount
        conn.commit()
        return count


def get_funnel_data(weeks: int = 12) -> list[dict]:
    """Weekly funnel: page views → signup clicks → signups → onboarded → first draft sent."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH week_series AS (
                SELECT generate_series(
                    date_trunc('week', now() - make_interval(weeks => %s)),
                    date_trunc('week', now()),
                    '1 week'::interval
                ) AS week
            ),
            page_views AS (
                SELECT date_trunc('week', created_at) AS week, count(*) AS cnt
                FROM page_events
                WHERE event = 'landing_page_view'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            signup_clicks AS (
                SELECT date_trunc('week', created_at) AS week, count(*) AS cnt
                FROM page_events
                WHERE event = 'signup_click'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            signups AS (
                SELECT date_trunc('week', created_at) AS week, count(*) AS cnt
                FROM users
                WHERE created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            onboarded AS (
                SELECT date_trunc('week', created_at) AS week, count(DISTINCT user_id) AS cnt
                FROM analytics_events
                WHERE event = 'onboarding_completed'
                  AND created_at >= now() - make_interval(weeks => %s)
                GROUP BY 1
            ),
            first_drafts AS (
                SELECT date_trunc('week', min_sent) AS week, count(*) AS cnt
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
            (weeks, weeks, weeks, weeks, weeks, weeks),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_cohort_data(weeks: int = 8) -> dict:
    """Rich cohort data: retention by week offset, plus absolute-date series for emails/active/actions."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH cohorts AS (
                SELECT id AS user_id, date_trunc('week', created_at) AS cohort_week
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
                    date_trunc('week', ae.created_at) AS activity_week,
                    FLOOR(EXTRACT(EPOCH FROM date_trunc('week', ae.created_at) - c.cohort_week) / 604800)::int AS week_offset,
                    count(DISTINCT c.user_id) AS active_users,
                    count(*) FILTER (WHERE ae.event = 'draft_sent') AS emails_sent,
                    count(*) AS total_actions
                FROM cohorts c
                JOIN analytics_events ae ON ae.user_id = c.user_id
                WHERE ae.event IN ('draft_composed', 'draft_sent', 'email_classified', 'setting_changed')
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
            (weeks,),
        )
        cols = [desc[0] for desc in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        # Build per-cohort data
        cohort_map: dict[str, dict] = {}
        all_activity_weeks: set[str] = set()
        for row in rows:
            key = str(row["cohort_week"])
            if key not in cohort_map:
                cohort_map[key] = {
                    "week": key,
                    "size": row["size"],
                    "by_offset": {},   # week_offset -> {active_users, ...}
                    "by_date": {},     # activity_week ISO -> {active_users, emails_sent, total_actions}
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
        max_offset = max(
            (max(c["by_offset"].keys()) for c in cohorts if c["by_offset"]),
            default=0,
        )
        sorted_activity_weeks = sorted(all_activity_weeks)

        # Build retention arrays (by week offset) — week 0 = 100% by definition
        result_cohorts = []
        for c in cohorts:
            size = c["size"]
            retention = []
            for i in range(int(max_offset) + 1):
                if i == 0:
                    retention.append(100.0)
                else:
                    w = c["by_offset"].get(i, {})
                    active = w.get("active_users", 0)
                    retention.append(round(active / size * 100, 1) if size > 0 else 0)

            # Cumulative actions for lifetime chart (by offset, averaged per user)
            lifetime_actions = []
            cumulative = 0
            for i in range(int(max_offset) + 1):
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
                email_point[label] = d.get("emails_sent", 0)
                active_point[label] = d.get("active_users", 0)
            emails_by_week.append(email_point)
            active_by_week.append(active_point)

        return {
            "cohorts": result_cohorts,
            "max_weeks": int(max_offset) + 1,
            "emails_by_week": emails_by_week,
            "active_by_week": active_by_week,
        }


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
                   cd.composed_at, cd.sent_at, cd.thread_context
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
