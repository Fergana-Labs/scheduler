"""Database client – Firestore backend."""

import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from google.cloud import firestore

from scheduler.config import config

# ---------------------------------------------------------------------------
# Firestore client (lazy singleton)
# ---------------------------------------------------------------------------

_db: firestore.Client | None = None


def _get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _doc_to_user(doc_dict: dict) -> UserRow:
    """Convert a Firestore document dict to a UserRow, ignoring extra fields."""
    valid_fields = set(UserRow.__dataclass_fields__)
    return UserRow(**{k: v for k, v in doc_dict.items() if k in valid_fields})


def _user_ref(email: str):
    """Reference to users/{email}."""
    return _get_db().collection("users").document(email)


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


def get_user_by_email(email: str) -> UserRow | None:
    doc = _user_ref(email).get()
    if not doc.exists:
        return None
    return _doc_to_user(doc.to_dict())


def get_user_by_id(user_id: str) -> UserRow | None:
    """Find a user by their UUID. Scans the users collection."""
    docs = (
        _get_db()
        .collection("users")
        .where("id", "==", user_id)
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_user(doc.to_dict())
    return None


def upsert_user(
    email: str,
    google_refresh_token: str,
    google_access_token: str | None = None,
    access_token_expires_at: datetime | None = None,
    scheduled_calendar_id: str | None = None,
) -> tuple[UserRow, bool]:
    """Upsert a user. Returns (user, is_new)."""
    ref = _user_ref(email)
    doc = ref.get()
    now = _now()

    if doc.exists:
        updates = {
            "google_refresh_token": google_refresh_token,
            "google_access_token": google_access_token,
            "access_token_expires_at": access_token_expires_at,
            "updated_at": now,
        }
        if scheduled_calendar_id is not None:
            updates["scheduled_calendar_id"] = scheduled_calendar_id
        ref.update(updates)
        return _doc_to_user(ref.get().to_dict()), False

    # New user
    data = {
        "id": str(uuid.uuid4()),
        "email": email,
        "google_refresh_token": google_refresh_token,
        "google_access_token": google_access_token,
        "access_token_expires_at": access_token_expires_at,
        "scheduled_calendar_id": scheduled_calendar_id,
        "gmail_history_id": None,
        "system_enabled": True,
        "scheduled_branding_enabled": True,
        "autopilot_enabled": False,
        "process_sales_emails": False,
        "reasoning_emails_enabled": False,
        "calendar_ids": None,
        "onboarding_status": None,
        "created_at": now,
        "updated_at": now,
    }
    ref.set(data)
    return _doc_to_user(data), True


def _update_user_field(user_id: str, **fields) -> None:
    """Find user by id and update the given fields + updated_at."""
    docs = (
        _get_db()
        .collection("users")
        .where("id", "==", user_id)
        .limit(1)
        .stream()
    )
    for doc in docs:
        doc.reference.update({**fields, "updated_at": _now()})
        return


def update_user_tokens(
    user_id: str,
    google_access_token: str,
    access_token_expires_at: datetime | None = None,
) -> None:
    _update_user_field(
        user_id,
        google_access_token=google_access_token,
        access_token_expires_at=access_token_expires_at,
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
        access_token_expires_at=access_token_expires_at,
    )


def get_all_user_ids() -> list[str]:
    docs = _get_db().collection("users").select(["id"]).stream()
    return [doc.to_dict()["id"] for doc in docs]


def update_scheduled_branding(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, scheduled_branding_enabled=enabled)


def update_system_enabled(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, system_enabled=enabled)


def update_autopilot(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, autopilot_enabled=enabled)


def update_process_sales_emails(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, process_sales_emails=enabled)


def update_reasoning_emails_enabled(user_id: str, enabled: bool) -> None:
    _update_user_field(user_id, reasoning_emails_enabled=enabled)


def update_scheduled_calendar_id(user_id: str, scheduled_calendar_id: str) -> None:
    _update_user_field(user_id, scheduled_calendar_id=scheduled_calendar_id)


def update_calendar_ids(user_id: str, calendar_ids: list[str]) -> None:
    _update_user_field(user_id, calendar_ids=calendar_ids)


def update_onboarding_status(user_id: str, status: str | None) -> None:
    _update_user_field(user_id, onboarding_status=status)


def delete_user(user_id: str) -> None:
    """Delete user and all subcollections."""
    docs = (
        _get_db()
        .collection("users")
        .where("id", "==", user_id)
        .limit(1)
        .stream()
    )
    for doc in docs:
        # Delete guides subcollection
        for guide in doc.reference.collection("guides").stream():
            guide.reference.delete()
        # Delete pending_invites subcollection
        for invite in doc.reference.collection("pending_invites").stream():
            invite.reference.delete()
        # Delete processed_messages subcollection
        for msg in doc.reference.collection("processed_messages").stream():
            msg.reference.delete()
        doc.reference.delete()


def disconnect_user(user_id: str) -> None:
    """Clear Google tokens and delete guides, but keep the user doc."""
    docs = (
        _get_db()
        .collection("users")
        .where("id", "==", user_id)
        .limit(1)
        .stream()
    )
    for doc in docs:
        # Delete guides subcollection
        for guide in doc.reference.collection("guides").stream():
            guide.reference.delete()

        doc.reference.update({
            "google_refresh_token": None,
            "google_access_token": None,
            "access_token_expires_at": None,
            "gmail_history_id": None,
            "scheduled_calendar_id": None,
            "onboarding_status": None,
            "updated_at": _now(),
        })


# ---------------------------------------------------------------------------
# Guides  (subcollection: users/{email}/guides/{guide_name})
# ---------------------------------------------------------------------------


def _guide_ref(user_id: str, name: str):
    """Get guide doc ref. Looks up user email by user_id first."""
    user = get_user_by_id(user_id)
    if not user:
        return None
    return _user_ref(user.email).collection("guides").document(name)


def _guides_collection(user_id: str):
    """Get guides collection ref for a user."""
    user = get_user_by_id(user_id)
    if not user:
        return None
    return _user_ref(user.email).collection("guides")


def upsert_guide(user_id: str, name: str, content: str) -> GuideRow:
    ref = _guide_ref(user_id, name)
    now = _now()

    doc = ref.get()
    if doc.exists:
        ref.update({"content": content, "updated_at": now})
        return GuideRow(**ref.get().to_dict())

    data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": name,
        "content": content,
        "created_at": now,
        "updated_at": now,
    }
    ref.set(data)
    return GuideRow(**data)


def get_guide(user_id: str, name: str) -> GuideRow | None:
    ref = _guide_ref(user_id, name)
    if ref is None:
        return None
    doc = ref.get()
    if not doc.exists:
        return None
    return GuideRow(**doc.to_dict())


def get_guides_for_user(user_id: str) -> list[GuideRow]:
    col = _guides_collection(user_id)
    if col is None:
        return []
    docs = col.order_by("name").stream()
    return [GuideRow(**doc.to_dict()) for doc in docs]


# ---------------------------------------------------------------------------
# Processed messages  (subcollection: users/{email}/processed_messages/{msg_id})
# ---------------------------------------------------------------------------


def try_claim_message(user_id: str, message_id: str) -> bool:
    """Atomically claim a message using a Firestore transaction.

    Returns True if this call claimed it, False if already claimed.
    """
    user = get_user_by_id(user_id)
    if not user:
        return False

    ref = (
        _user_ref(user.email)
        .collection("processed_messages")
        .document(message_id)
    )

    db = _get_db()
    transaction = db.transaction()

    @firestore.transactional
    def _claim(txn, doc_ref):
        snapshot = doc_ref.get(transaction=txn)
        if snapshot.exists:
            return False
        txn.set(doc_ref, {
            "user_id": user_id,
            "message_id": message_id,
            "processed_at": _now(),
        })
        return True

    return _claim(transaction, ref)


def cleanup_processed_messages(days: int = 7) -> int:
    """Delete processed message records older than the given number of days."""
    cutoff = _now() - timedelta(days=days)
    count = 0

    for user_doc in _get_db().collection("users").stream():
        msgs = (
            user_doc.reference.collection("processed_messages")
            .where("processed_at", "<", cutoff)
            .stream()
        )
        for msg in msgs:
            msg.reference.delete()
            count += 1

    return count


# ---------------------------------------------------------------------------
# Pending invites  (subcollection: users/{email}/pending_invites/{thread_id})
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
    user = get_user_by_id(user_id)
    ref = _user_ref(user.email).collection("pending_invites").document(thread_id)
    now = _now()

    data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "thread_id": thread_id,
        "attendee_emails": attendee_emails,
        "event_summary": event_summary,
        "event_start": event_start,
        "event_end": event_end,
        "add_google_meet": add_google_meet,
        "location": location,
        "created_at": now,
    }
    ref.set(data)
    return PendingInviteRow(**data)


def get_pending_invite_by_thread(user_id: str, thread_id: str) -> PendingInviteRow | None:
    user = get_user_by_id(user_id)
    if not user:
        return None
    ref = _user_ref(user.email).collection("pending_invites").document(thread_id)
    doc = ref.get()
    if not doc.exists:
        return None
    return PendingInviteRow(**doc.to_dict())


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
        updates["attendee_emails"] = attendee_emails
    if event_summary is not None:
        updates["event_summary"] = event_summary
    if event_start is not None:
        updates["event_start"] = event_start
    if event_end is not None:
        updates["event_end"] = event_end
    if add_google_meet is not None:
        updates["add_google_meet"] = add_google_meet
    if location is not None:
        updates["location"] = location
    if not updates:
        return

    # Search all users' pending_invites for matching invite_id
    for user_doc in _get_db().collection("users").stream():
        invites = (
            user_doc.reference.collection("pending_invites")
            .where("id", "==", invite_id)
            .limit(1)
            .stream()
        )
        for invite_doc in invites:
            invite_doc.reference.update(updates)
            return


def delete_pending_invite(invite_id: str) -> None:
    """Delete a pending invite by its UUID."""
    for user_doc in _get_db().collection("users").stream():
        invites = (
            user_doc.reference.collection("pending_invites")
            .where("id", "==", invite_id)
            .limit(1)
            .stream()
        )
        for invite_doc in invites:
            invite_doc.reference.delete()
            return
