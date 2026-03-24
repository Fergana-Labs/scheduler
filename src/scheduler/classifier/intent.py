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
from typing import Any, TypedDict, Literal

from anthropic import Anthropic

from scheduler.config import config


class SchedulingIntent(Enum):
    """Classification result for an email."""

    NOT_SCHEDULING = "not_scheduling"  # Email is not about scheduling
    REQUESTING_MEETING = "requesting_meeting"  # Someone wants to meet with the user
    PROPOSING_TIMES = "proposing_times"  # Someone is proposing specific times
    CONFIRMING_TIME = "confirming_time"  # Someone is confirming a previously discussed time
    CANCELLING_RESCHEDULING = "cancelling_rescheduling"  # Someone is cancelling or rescheduling


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
    intent: Literal[
        "not_scheduling",
        "requesting_meeting",
        "proposing_times",
        "confirming_time",
        "cancelling_rescheduling",
    ]
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

    system_prompt = (
        "You are a classifier for scheduling-related emails. "
        "Given an email subject, body, sender, and the prior thread history, "
        "you must determine whether the email is about scheduling a meeting, "
        "and if so, extract structured details.\n\n"
        "Focus your classification on the LATEST message, but use the thread history "
        "to understand context (e.g. what was previously discussed, proposed, or agreed to).\n\n"
        "Valid intents:\n"
        "- not_scheduling: Email is not about scheduling at all.\n"
        "- requesting_meeting: Someone wants to meet with the user.\n"
        "- proposing_times: Someone proposes one or more specific times.\n"
        "- confirming_time: Someone confirms a previously discussed time.\n"
        "- cancelling_rescheduling: Someone is cancelling or rescheduling a previously agreed meeting.\n\n"
        "You MUST respond with a single JSON object only, no prose, matching this schema:\n"
        "{\n"
        '  \"intent\": \"not_scheduling\" | \"requesting_meeting\" | \"proposing_times\" | \"confirming_time\" | \"cancelling_rescheduling\",\n'
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
        "Multi-day events (conferences, retreats, offsites, summits, multi-day workshops, etc.) "
        "are NOT scheduling requests — classify them as \"not_scheduling\". We only handle "
        "single meetings/calls, not multi-day commitments.\n\n"
        "Automated calendar invites and notifications (e.g. from Google Calendar, Outlook, "
        "Calendly, or other scheduling tools) are NOT scheduling requests — classify them "
        "as \"not_scheduling\". These are system-generated notifications, not personal emails "
        "that need a response.\n\n"
        "Group announcements and broadcast emails are NOT scheduling requests — classify them "
        "as \"not_scheduling\". Signs of a group announcement include: the email is addressed "
        "to a group (\"Hi Founders\", \"Hi everyone\", \"Hi team\"), the user is BCC'd or not "
        "in the To/CC fields, the sender is informing a group about an event rather than "
        "personally requesting the user to meet, or the email is a newsletter/community update. "
        "These are one-to-many communications, not personal scheduling requests.\n\n"
        "If the email is not about scheduling, set intent to \"not_scheduling\" and leave\n"
        "the other fields as your best-effort defaults."
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
        # On any failure, fall back to NOT_SCHEDULING with minimal info.
        return ClassificationResult(
            intent=SchedulingIntent.NOT_SCHEDULING,
            confidence=0.0,
            summary="",
            proposed_times=[],
            participants=[],
            duration_minutes=None,
            is_sales_email=False,
        )

    intent_str = data.get("intent", "not_scheduling")
    intent = SchedulingIntent(intent_str) if intent_str in SchedulingIntent._value2member_map_ else SchedulingIntent.NOT_SCHEDULING

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


