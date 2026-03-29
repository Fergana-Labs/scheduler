"""LLM completion classifier for scheduling intent in emails.

This is a simple LLM completion (not an agent) — it takes an email and returns
a structured classification. No tools, no agentic loop, just a single API call
with structured output.

Determines whether an incoming email is asking the user to schedule something,
and if so, extracts relevant details (proposed times, urgency, etc.).
"""

from dataclasses import dataclass
from enum import Enum
import json
import logging
from typing import Any, TypedDict, Literal

from anthropic import Anthropic

from scheduler.config import config

logger = logging.getLogger(__name__)


class SchedulingIntent(Enum):
    """Binary: does this email need a draft reply or not?"""

    NEEDS_DRAFT = "needs_draft"
    DOESNT_NEED_DRAFT = "doesnt_need_draft"


@dataclass
class ClassificationResult:
    """Result of classifying an email for scheduling intent."""

    intent: SchedulingIntent
    confidence: float  # 0.0 to 1.0
    summary: str  # Brief description of what's being scheduled
    proposed_times: list[str]  # Any specific times mentioned in the email
    participants: list[str]  # People involved in the meeting
    duration_minutes: int | None  # Estimated meeting duration if mentioned
    is_sales_email: bool = False  # Whether the email is sales-oriented


class _EmailClassificationJSON(TypedDict, total=False):
    intent: Literal["needs_draft", "doesnt_need_draft"]
    confidence: float
    summary: str
    proposed_times: list[str]
    participants: list[str]
    duration_minutes: int | None
    is_sales_email: bool


class _EventJSON(TypedDict, total=False):
    summary: str
    start_iso: str
    duration_minutes: int
    participants: list[str]


def _get_anthropic_client() -> Anthropic:
    """Create an Anthropic client using the configured API key.

    Even though we conceptually talk about \"GPT\" in the design,
    this project already depends on Anthropic and the Claude Agent SDK,
    so we reuse Anthropic here for simple single-call classifiers.
    """
    if not config.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return Anthropic(api_key=config.anthropic_api_key)


def classify_email(
    subject: str,
    body: str,
    sender: str,
    thread_messages: list[dict],
    recipient: str = "",
    cc: str = "",
    user_email: str = "",
) -> ClassificationResult:
    """Classify whether an email is about scheduling a meeting.

    Args:
        subject: Email subject line.
        body: Email body text (the latest message to classify).
        sender: Sender's email address.
        thread_messages: Prior messages in the thread (oldest first), each with
            'sender', 'body', and optionally 'date' keys. Gives the classifier
            full conversation context.
        recipient: To field (who the email is addressed to).
        cc: CC field.

    Returns:
        ClassificationResult with the intent and extracted details.
    """
    client = _get_anthropic_client()

    user_line = f"The user's email address is {user_email}. " if user_email else ""
    system_prompt = (
        "You are a classifier that decides whether an email needs a scheduling draft reply.\n\n"
        f"{user_line}"
        "Given an email subject, body, sender, and the prior thread history, "
        "decide: does this email need the user to take a scheduling action "
        "(propose times, accept/decline, reschedule, etc.)? If yes, intent is \"needs_draft\". "
        "If no, intent is \"doesnt_need_draft\".\n\n"
        "Focus your classification on the LATEST message, but use the thread history "
        "to understand context (e.g. what was previously discussed, proposed, or agreed to).\n\n"
        "needs_draft examples:\n"
        "- Someone requests a meeting in a personal email\n"
        "- Someone proposes specific times\n"
        "- Someone confirms a time (user may need to send a calendar invite or acknowledge)\n"
        "- Someone cancels or reschedules in a personal email (user may need to propose new times)\n\n"
        "doesnt_need_draft examples:\n"
        "- Email is not about scheduling at all\n"
        "- Newsletters, product updates, marketing emails\n"
        "- Support questions unrelated to scheduling\n"
        "- Multi-day events (conferences, retreats, offsites, summits)\n"
        "- Group announcements addressed to many people (\"Hi Founders\", \"Hi everyone\")\n"
        "- The user is only CC'd and someone else is the primary recipient\n"
        "- Automated calendar notifications (Google Calendar reminders, event updates, cancellations, daily agendas)\n"
        "- Automated calendar invites (\"has invited you to the following event\", \"Going: yes/maybe/no\")\n"
        "- Booking confirmations from scheduling tools (Calendly, Cal.com, Zoom) — the meeting is already booked\n"
        "- Any system-generated email about a meeting that was already scheduled — no human is waiting for a reply\n\n"
        "You MUST respond with a single JSON object only, no prose, matching this schema:\n"
        "{\n"
        '  \"intent\": \"needs_draft\" | \"doesnt_need_draft\",\n'
        "  \"confidence\": number between 0 and 1,\n"
        "  \"summary\": string,\n"
        "  \"proposed_times\": list of strings,\n"
        "  \"participants\": list of strings,\n"
        "  \"duration_minutes\": integer minutes or null,\n"
        "  \"is_sales_email\": boolean\n"
        "}\n"
        "\"is_sales_email\": true if the email is UNSOLICITED COLD OUTREACH — "
        "sales pitches, product demos, partnership proposals, investor/VC intros, "
        "fundraising outreach, recruiting cold emails, or any email where a stranger "
        "is trying to get a meeting without a prior relationship. Do NOT flag replies "
        "to the user's own outreach, or emails from known contacts. If in doubt, set false.\n\n"
        "If the email doesnt_need_draft, leave the other fields as your best-effort defaults."
    )

    # Build thread history section
    thread_section = ""
    if thread_messages:
        thread_section = "--- Thread history (oldest first) ---\n"
        for msg in thread_messages:
            date_str = msg.get("date", "")
            date_line = f" ({date_str})" if date_str else ""
            thread_section += f"From: {msg['sender']}{date_line}\n{msg['body']}\n\n"
        thread_section += "--- End of thread history ---\n\n"

    recipient_line = f"To: {recipient}\n" if recipient else ""
    cc_line = f"CC: {cc}\n" if cc else ""

    user_content = (
        "Classify the following email for scheduling intent.\n\n"
        f"{thread_section}"
        f"LATEST MESSAGE (classify this):\n"
        f"Sender: {sender}\n"
        f"{recipient_line}"
        f"{cc_line}"
        f"Subject: {subject}\n\n"
        f"Body:\n{body}\n"
    )

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        # We expect a single text block with JSON.
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text += block.text

        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]  # remove opening ```json
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        data: _EmailClassificationJSON = json.loads(text)
    except Exception:
        logger.error("classify_email: LLM call failed for subject=%r sender=%r, falling back to doesnt_need_draft", subject, sender, exc_info=True)
        return ClassificationResult(
            intent=SchedulingIntent.DOESNT_NEED_DRAFT,
            confidence=0.0,
            summary="",
            proposed_times=[],
            participants=[],
            duration_minutes=None,
            is_sales_email=False,
        )

    intent_str = data.get("intent", "doesnt_need_draft")
    try:
        intent = SchedulingIntent(intent_str)
    except ValueError:
        intent = SchedulingIntent.DOESNT_NEED_DRAFT

    confidence = float(data.get("confidence", 0.0))
    summary = data.get("summary") or ""
    proposed_times = list(data.get("proposed_times") or [])
    participants = list(data.get("participants") or [])
    duration_raw = data.get("duration_minutes", None)
    duration_minutes: int | None
    try:
        duration_minutes = int(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration_minutes = None

    is_sales_email = bool(data.get("is_sales_email", False))

    return ClassificationResult(
        intent=intent,
        confidence=confidence,
        summary=summary,
        proposed_times=proposed_times,
        participants=participants,
        duration_minutes=duration_minutes,
        is_sales_email=is_sales_email,
    )


@dataclass
class InviteVerificationResult:
    """Result of verifying whether a sent message still confirms a pending invite."""

    action: str  # "send" | "update" | "skip"
    reason: str
    updated_attendee_emails: list[str] | None = None
    updated_event_summary: str | None = None
    updated_event_start: str | None = None  # ISO 8601
    updated_event_end: str | None = None  # ISO 8601
    updated_add_google_meet: bool | None = None
    updated_location: str | None = None


def verify_sent_message_for_invite(
    sent_message_body: str,
    sent_message_sender: str,
    thread_messages: list[dict],
    pending_invite: Any,
) -> InviteVerificationResult:
    """Verify whether a user's sent message still confirms a pending calendar invite.

    Compares the sent message against the pending invite details and the thread
    context. Returns whether to send the invite as-is, update it, or skip it.
    """
    client = _get_anthropic_client()

    system_prompt = (
        "You are verifying whether a sent email still confirms a proposed calendar invite.\n\n"
        "You are given:\n"
        "1. A pending calendar invite proposal (attendees, time, summary, location)\n"
        "2. The full email thread history\n"
        "3. The message the user just sent\n\n"
        "Your job: decide whether the user's sent message confirms, modifies, or cancels "
        "the proposed meeting.\n\n"
        "Return a single JSON object with these fields:\n"
        "{\n"
        '  "action": "send" | "update" | "skip",\n'
        '  "reason": string explaining your decision,\n'
        '  "updated_attendee_emails": list of strings | null,\n'
        '  "updated_event_summary": string | null,\n'
        '  "updated_event_start": string (ISO 8601) | null,\n'
        '  "updated_event_end": string (ISO 8601) | null,\n'
        '  "updated_add_google_meet": boolean | null,\n'
        '  "updated_location": string | null\n'
        "}\n\n"
        "Actions:\n"
        '- "send": The sent message confirms the meeting as proposed. No changes needed.\n'
        '- "update": The sent message confirms a meeting but details changed (different time, '
        "attendees, location, summary, etc.). Populate the updated_* fields with the new values. "
        "Only include fields that changed — leave others null. For updated_attendee_emails, "
        "provide the FULL list of attendee emails (not just added/removed ones).\n"
        '- "skip": The sent message declines, cancels, changes the topic, or does not confirm '
        "any meeting. The invite should NOT be sent.\n\n"
        "Be conservative: if there is any ambiguity about whether the user is confirming the "
        "meeting, choose skip. It is much better to not send an invite than to send an unwanted one.\n\n"
        "Only return the JSON object, no prose."
    )

    thread_section = ""
    if thread_messages:
        thread_section = "--- Thread history (oldest first) ---\n"
        for msg in thread_messages:
            date_str = msg.get("date", "")
            date_line = f" ({date_str})" if date_str else ""
            thread_section += f"From: {msg['sender']}{date_line}\n{msg['body']}\n\n"
        thread_section += "--- End of thread history ---\n\n"

    attendees_str = ", ".join(pending_invite.attendee_emails)
    location_str = pending_invite.location or "(none)"

    user_content = (
        "Verify whether this sent message confirms the proposed calendar invite.\n\n"
        f"PENDING INVITE PROPOSAL:\n"
        f"  Attendees: {attendees_str}\n"
        f"  Summary: {pending_invite.event_summary}\n"
        f"  Start: {pending_invite.event_start.isoformat()}\n"
        f"  End: {pending_invite.event_end.isoformat()}\n"
        f"  Location: {location_str}\n"
        f"  Google Meet: {pending_invite.add_google_meet}\n\n"
        f"{thread_section}"
        f"SENT MESSAGE (from {sent_message_sender}):\n"
        f"{sent_message_body}\n"
    )

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        data: dict = json.loads(text.strip())
    except Exception:
        # Safe fallback: never send an invite on error
        return InviteVerificationResult(action="skip", reason="verification failed due to error")

    action = data.get("action", "skip")
    if action not in ("send", "update", "skip"):
        action = "skip"

    return InviteVerificationResult(
        action=action,
        reason=data.get("reason", ""),
        updated_attendee_emails=data.get("updated_attendee_emails"),
        updated_event_summary=data.get("updated_event_summary"),
        updated_event_start=data.get("updated_event_start"),
        updated_event_end=data.get("updated_event_end"),
        updated_add_google_meet=data.get("updated_add_google_meet"),
        updated_location=data.get("updated_location"),
    )


def classify_message_for_event(message: str, sender: str) -> dict | None:
    """Classify whether a message (text, Slack, etc.) creates a new event.

    Used by the ongoing message hook to detect commitments made outside email.

    Args:
        message: The message text.
        sender: Who sent it.

    Returns:
        Dict with event details (summary, datetime, duration) if a new event
        was detected, None otherwise.
    """
    client = _get_anthropic_client()

    system_prompt = (
        "You are a classifier that decides whether a single message represents a concrete "
        "scheduling commitment that should be added to a calendar.\n\n"
        "If the message does NOT clearly specify a time window for a real-world commitment "
        "(meeting, call, dinner, etc.), you must respond with the literal JSON value null.\n\n"
        "If it DOES represent a concrete commitment, respond with a single JSON object only, "
        "matching this schema:\n"
        "{\n"
        "  \"summary\": string,              // what the event is about\n"
        "  \"start_iso\": string,           // ISO 8601 start datetime\n"
        "  \"duration_minutes\": integer,   // duration in minutes\n"
        "  \"participants\": [string]       // optional names/emails/handles\n"
        "}\n"
        "Do not include any other fields. Do not include any explanation."
    )

    user_content = (
        "Decide whether the following message represents a concrete scheduling commitment.\n\n"
        f"Sender: {sender}\n"
        f"Message:\n{message}\n"
    )

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text += block.text

        text_stripped = text.strip()
        if text_stripped.startswith("```"):
            text_stripped = text_stripped.split("\n", 1)[1]
        if text_stripped.endswith("```"):
            text_stripped = text_stripped.rsplit("```", 1)[0]
        text_stripped = text_stripped.strip()

        if text_stripped == "null":
            return None

        data: _EventJSON = json.loads(text_stripped)

        summary = data.get("summary")
        start_iso = data.get("start_iso")
        duration_minutes = data.get("duration_minutes")
        if not isinstance(summary, str) or not isinstance(start_iso, str) or not isinstance(
            duration_minutes, int
        ):
            return None

        participants = data.get("participants") or []
        participants = [str(p) for p in participants]

        return {
            "summary": summary,
            "start_iso": start_iso,
            "duration_minutes": duration_minutes,
            "participants": participants,
        }
    except Exception:
        return None


