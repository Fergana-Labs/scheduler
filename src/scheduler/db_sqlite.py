"""Database client – SQLite backend with optional GCS persistence."""

import json
import logging
import sqlite3
import threading
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path

import google.auth
import google.auth.transport.requests

from scheduler.config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GCS sync — download on startup, upload after writes
# ---------------------------------------------------------------------------

_GCS_BLOB = "scheduler.db"
_upload_lock = threading.Lock()


def _gcs_token() -> str:
    credentials, _ = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def _gcs_download() -> None:
    """Download the SQLite DB from GCS if it exists."""
    if not config.gcs_bucket:
        return
    try:
        url = f"https://storage.googleapis.com/storage/v1/b/{config.gcs_bucket}/o/{_GCS_BLOB}?alt=media"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_gcs_token()}"})
        data = urllib.request.urlopen(req).read()
        Path(config.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(config.sqlite_db_path).write_bytes(data)
        logger.info("gcs_sync: downloaded %d bytes from gs://%s/%s", len(data), config.gcs_bucket, _GCS_BLOB)
    except Exception as e:
        if "404" in str(e):
            logger.info("gcs_sync: no existing DB in GCS, starting fresh")
        else:
            logger.warning("gcs_sync: download failed: %s", e)


def _do_gcs_upload() -> None:
    with _upload_lock:
        try:
            data = Path(config.sqlite_db_path).read_bytes()
            url = f"https://storage.googleapis.com/upload/storage/v1/b/{config.gcs_bucket}/o?uploadType=media&name={_GCS_BLOB}"
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "Authorization": f"Bearer {_gcs_token()}",
                "Content-Type": "application/octet-stream",
            })
            urllib.request.urlopen(req)
            logger.debug("gcs_sync: uploaded %d bytes to gs://%s/%s", len(data), config.gcs_bucket, _GCS_BLOB)
        except Exception:
            logger.warning("gcs_sync: upload failed", exc_info=True)


def _gcs_upload() -> None:
    """Upload the SQLite DB to GCS in background."""
    if not config.gcs_bucket:
        return
    threading.Thread(target=_do_gcs_upload, daemon=True).start()


# ---------------------------------------------------------------------------
# SQLite connection (lazy singleton)
# ---------------------------------------------------------------------------

_conn: sqlite3.Connection | None = None


def _get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _gcs_download()
        Path(config.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.sqlite_db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            google_refresh_token TEXT,
            google_access_token TEXT,
            access_token_expires_at TEXT,
            scheduled_calendar_id TEXT,
            gmail_history_id TEXT,
            system_enabled INTEGER NOT NULL DEFAULT 1,
            scheduled_branding_enabled INTEGER NOT NULL DEFAULT 1,
            autopilot_enabled INTEGER NOT NULL DEFAULT 0,
            process_sales_emails INTEGER NOT NULL DEFAULT 0,
            reasoning_emails_enabled INTEGER NOT NULL DEFAULT 0,
            calendar_ids TEXT,
            onboarding_status TEXT,
            display_name TEXT,
            draft_auto_delete_enabled INTEGER NOT NULL DEFAULT 1,
            google_email TEXT,
            scheduling_mode TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS guides (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, name)
        );

        CREATE TABLE IF NOT EXISTS processed_messages (
            user_id TEXT NOT NULL REFERENCES users(id),
            message_id TEXT NOT NULL,
            processed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, message_id)
        );

        CREATE TABLE IF NOT EXISTS pending_invites (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            thread_id TEXT NOT NULL,
            attendee_emails TEXT NOT NULL,
            event_summary TEXT NOT NULL,
            event_start TEXT NOT NULL,
            event_end TEXT NOT NULL,
            add_google_meet INTEGER NOT NULL DEFAULT 0,
            location TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(user_id, thread_id)
        );

        CREATE TABLE IF NOT EXISTS bot_account (
            id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            gmail_history_id TEXT,
            watch_expiration INTEGER,
            updated_at TEXT
        );
        INSERT OR IGNORE INTO bot_account (id, updated_at) VALUES (1, datetime('now'));

        CREATE TABLE IF NOT EXISTS bot_conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            thread_id TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'new',
            participants TEXT NOT NULL DEFAULT '[]',
            counterparty_email TEXT,
            event_summary TEXT,
            duration_minutes INTEGER,
            proposed_windows TEXT NOT NULL DEFAULT '[]',
            declined_windows TEXT NOT NULL DEFAULT '[]',
            constraints TEXT NOT NULL DEFAULT '[]',
            turn_count INTEGER NOT NULL DEFAULT 0,
            last_bot_reply_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT,
            UNIQUE(user_id, thread_id)
        );

        CREATE TABLE IF NOT EXISTS bot_processed_messages (
            message_id TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        );
    """)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


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
    calendar_ids: list[str] | None = None
    onboarding_status: str | None = None
    display_name: str | None = None
    draft_auto_delete_enabled: bool = True
    google_email: str | None = None
    scheduling_mode: str = "draft"


@dataclass
class GuideRow:
    id: str
    user_id: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _commit(db: sqlite3.Connection) -> None:
    """Commit and sync to GCS in background."""
    db.commit()
    _gcs_upload()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _parse_ts(val: str | None) -> datetime | None:
    if val is None:
        return None
    return datetime.fromisoformat(val)


def _row_to_user(row: sqlite3.Row) -> UserRow:
    return UserRow(
        id=row["id"],
        email=row["email"],
        google_refresh_token=row["google_refresh_token"],
        google_access_token=row["google_access_token"],
        access_token_expires_at=_parse_ts(row["access_token_expires_at"]),
        scheduled_calendar_id=row["scheduled_calendar_id"],
        gmail_history_id=row["gmail_history_id"],
        system_enabled=bool(row["system_enabled"]),
        scheduled_branding_enabled=bool(row["scheduled_branding_enabled"]),
        autopilot_enabled=bool(row["autopilot_enabled"]),
        process_sales_emails=bool(row["process_sales_emails"]),
        reasoning_emails_enabled=bool(row["reasoning_emails_enabled"]),
        calendar_ids=json.loads(row["calendar_ids"]) if row["calendar_ids"] else None,
        onboarding_status=row["onboarding_status"],
        display_name=row["display_name"],
        draft_auto_delete_enabled=bool(row["draft_auto_delete_enabled"]),
        google_email=row["google_email"],
        created_at=_parse_ts(row["created_at"]),
        updated_at=_parse_ts(row["updated_at"]),
    )


def _row_to_guide(row: sqlite3.Row) -> GuideRow:
    return GuideRow(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        content=row["content"],
        created_at=_parse_ts(row["created_at"]),
        updated_at=_parse_ts(row["updated_at"]),
    )


def _row_to_invite(row: sqlite3.Row) -> PendingInviteRow:
    return PendingInviteRow(
        id=row["id"],
        user_id=row["user_id"],
        thread_id=row["thread_id"],
        attendee_emails=json.loads(row["attendee_emails"]),
        event_summary=row["event_summary"],
        event_start=_parse_ts(row["event_start"]),
        event_end=_parse_ts(row["event_end"]),
        add_google_meet=bool(row["add_google_meet"]),
        location=row["location"],
        created_at=_parse_ts(row["created_at"]),
    )


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


def get_user_by_email(email: str) -> UserRow | None:
    row = _get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def get_user_by_google_email(google_email: str) -> UserRow | None:
    row = _get_db().execute("SELECT * FROM users WHERE google_email = ?", (google_email,)).fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def get_user_by_id(user_id: str) -> UserRow | None:
    row = _get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    return _row_to_user(row)


def upsert_user(
    email: str,
    google_refresh_token: str,
    google_access_token: str | None = None,
    access_token_expires_at: datetime | None = None,
    scheduled_calendar_id: str | None = None,
) -> tuple[UserRow, bool]:
    """Upsert a user. Returns (user, is_new)."""
    db = _get_db()
    existing = get_user_by_email(email)
    now = _now()

    if existing:
        updates = {
            "google_refresh_token": google_refresh_token,
            "google_access_token": google_access_token,
            "access_token_expires_at": _ts(access_token_expires_at),
            "updated_at": _ts(now),
        }
        if scheduled_calendar_id is not None:
            updates["scheduled_calendar_id"] = scheduled_calendar_id

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        db.execute(
            f"UPDATE users SET {set_clause} WHERE email = ?",
            (*updates.values(), email),
        )
        _commit(db)
        return get_user_by_email(email), False

    user_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO users (id, email, google_refresh_token, google_access_token,
           access_token_expires_at, scheduled_calendar_id, gmail_history_id,
           system_enabled, scheduled_branding_enabled, autopilot_enabled,
           process_sales_emails, reasoning_emails_enabled, calendar_ids,
           onboarding_status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 0, 0, 0, ?, ?, ?, ?)""",
        (user_id, email, google_refresh_token, google_access_token,
         _ts(access_token_expires_at), scheduled_calendar_id, None,
         None, None, _ts(now), _ts(now)),
    )
    _commit(db)
    return get_user_by_email(email), True


def _update_user_field(user_id: str, **fields) -> None:
    """Update the given fields + updated_at for a user."""
    fields["updated_at"] = _ts(_now())
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    db = _get_db()
    db.execute(
        f"UPDATE users SET {set_clause} WHERE id = ?",
        (*fields.values(), user_id),
    )
    _commit(db)


def update_user_tokens(
    user_id: str,
    google_access_token: str,
    access_token_expires_at: datetime | None = None,
) -> None:
    _update_user_field(
        user_id,
        google_access_token=google_access_token,
        access_token_expires_at=_ts(access_token_expires_at),
    )


def update_gmail_history_id(user_id: str, history_id: str) -> None:
    _update_user_field(user_id, gmail_history_id=history_id)


def update_google_tokens(
    user_id: str,
    google_refresh_token: str,
    google_access_token: str | None = None,
    access_token_expires_at: datetime | None = None,
) -> None:
    _update_user_field(
        user_id,
        google_refresh_token=google_refresh_token,
        google_access_token=google_access_token,
        access_token_expires_at=_ts(access_token_expires_at),
    )


def get_all_user_ids() -> list[str]:
    rows = _get_db().execute("SELECT id FROM users").fetchall()
    return [row["id"] for row in rows]


def update_scheduled_branding(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, scheduled_branding_enabled=int(enabled))


def update_system_enabled(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, system_enabled=int(enabled))


def update_autopilot(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, autopilot_enabled=int(enabled))


def update_process_sales_emails(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, process_sales_emails=int(enabled))


def update_reasoning_emails_enabled(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, reasoning_emails_enabled=int(enabled))


def update_display_name(user_id: str, display_name: str) -> None:
    _update_user_field(user_id, display_name=display_name)


def update_google_email(user_id: str, google_email: str) -> None:
    _update_user_field(user_id, google_email=google_email)


def update_draft_auto_delete(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, draft_auto_delete_enabled=int(enabled))


def update_scheduled_calendar_id(user_id: str, scheduled_calendar_id: str) -> None:
    _update_user_field(user_id, scheduled_calendar_id=scheduled_calendar_id)


def update_calendar_ids(user_id: str, calendar_ids: list[str]) -> None:
    _update_user_field(user_id, calendar_ids=json.dumps(calendar_ids))


def update_onboarding_status(user_id: str, status: str | None) -> None:
    _update_user_field(user_id, onboarding_status=status)


def delete_user(user_id: str) -> None:
    """Delete user and all related data."""
    db = _get_db()
    db.execute("DELETE FROM guides WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM pending_invites WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM processed_messages WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    _commit(db)


def disconnect_user(user_id: str) -> None:
    """Clear Google tokens and delete guides, but keep the user doc."""
    db = _get_db()
    db.execute("DELETE FROM guides WHERE user_id = ?", (user_id,))
    _update_user_field(
        user_id,
        google_refresh_token=None,
        google_access_token=None,
        access_token_expires_at=None,
        gmail_history_id=None,
        scheduled_calendar_id=None,
        onboarding_status=None,
    )


# ---------------------------------------------------------------------------
# Guides
# ---------------------------------------------------------------------------


def upsert_guide(user_id: str, name: str, content: str) -> GuideRow:
    db = _get_db()
    now = _ts(_now())
    db.execute(
        """INSERT INTO guides (id, user_id, name, content, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, name) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at""",
        (str(uuid.uuid4()), user_id, name, content, now, now),
    )
    _commit(db)
    row = db.execute(
        "SELECT * FROM guides WHERE user_id = ? AND name = ?", (user_id, name)
    ).fetchone()
    return _row_to_guide(row)


def get_guide(user_id: str, name: str) -> GuideRow | None:
    row = _get_db().execute(
        "SELECT * FROM guides WHERE user_id = ? AND name = ?", (user_id, name)
    ).fetchone()
    if row is None:
        return None
    return _row_to_guide(row)


def get_guides_for_user(user_id: str) -> list[GuideRow]:
    rows = _get_db().execute(
        "SELECT * FROM guides WHERE user_id = ? ORDER BY name", (user_id,)
    ).fetchall()
    return [_row_to_guide(row) for row in rows]


# ---------------------------------------------------------------------------
# Processed messages
# ---------------------------------------------------------------------------


def try_claim_message(user_id: str, message_id: str) -> bool:
    """Atomically claim a message. Returns True if this call claimed it."""
    db = _get_db()
    try:
        db.execute(
            "INSERT INTO processed_messages (user_id, message_id, processed_at) VALUES (?, ?, ?)",
            (user_id, message_id, _ts(_now())),
        )
        _commit(db)
        return True
    except sqlite3.IntegrityError:
        return False


def cleanup_processed_messages(days: int = 7) -> int:
    """Delete processed message records older than the given number of days."""
    cutoff = _ts(_now() - timedelta(days=days))
    db = _get_db()
    cursor = db.execute(
        "DELETE FROM processed_messages WHERE processed_at < ?", (cutoff,)
    )
    _commit(db)
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Pending invites
# ---------------------------------------------------------------------------


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
    db = _get_db()
    invite_id = str(uuid.uuid4())
    now = _ts(_now())

    db.execute(
        "DELETE FROM pending_invites WHERE user_id = ? AND thread_id = ?",
        (user_id, thread_id),
    )
    db.execute(
        """INSERT INTO pending_invites (id, user_id, thread_id, attendee_emails,
           event_summary, event_start, event_end, add_google_meet, location, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (invite_id, user_id, thread_id, json.dumps(attendee_emails),
         event_summary, _ts(event_start), _ts(event_end), int(add_google_meet),
         location, now),
    )
    _commit(db)
    row = db.execute("SELECT * FROM pending_invites WHERE id = ?", (invite_id,)).fetchone()
    return _row_to_invite(row)


def get_pending_invite_by_thread(user_id: str, thread_id: str) -> PendingInviteRow | None:
    row = _get_db().execute(
        "SELECT * FROM pending_invites WHERE user_id = ? AND thread_id = ?",
        (user_id, thread_id),
    ).fetchone()
    if row is None:
        return None
    return _row_to_invite(row)


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
    updates: dict = {}
    if attendee_emails is not None:
        updates["attendee_emails"] = json.dumps(attendee_emails)
    if event_summary is not None:
        updates["event_summary"] = event_summary
    if event_start is not None:
        updates["event_start"] = _ts(event_start)
    if event_end is not None:
        updates["event_end"] = _ts(event_end)
    if add_google_meet is not None:
        updates["add_google_meet"] = int(add_google_meet)
    if location is not None:
        updates["location"] = location
    if not updates:
        return

    db = _get_db()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    db.execute(
        f"UPDATE pending_invites SET {set_clause} WHERE id = ?",
        (*updates.values(), invite_id),
    )
    _commit(db)


def delete_pending_invite(invite_id: str) -> None:
    db = _get_db()
    db.execute("DELETE FROM pending_invites WHERE id = ?", (invite_id,))
    _commit(db)
