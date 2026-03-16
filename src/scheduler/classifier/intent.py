"""LLM-based classifier for scheduling intent in emails.

Determines whether an incoming email is asking the user to schedule something,
and if so, extracts relevant details (proposed times, urgency, etc.).
"""

from dataclasses import dataclass
from enum import Enum

import anthropic

from scheduler.config import config


class SchedulingIntent(Enum):
    """Classification result for an email."""

    NOT_SCHEDULING = "not_scheduling"  # Email is not about scheduling
    REQUESTING_MEETING = "requesting_meeting"  # Someone wants to meet with the user
    PROPOSING_TIMES = "proposing_times"  # Someone is proposing specific times
    CONFIRMING_TIME = "confirming_time"  # Someone is confirming a previously discussed time


@dataclass
class ClassificationResult:
    """Result of classifying an email for scheduling intent."""

    intent: SchedulingIntent
    confidence: float  # 0.0 to 1.0
    summary: str  # Brief description of what's being scheduled
    proposed_times: list[str]  # Any specific times mentioned in the email
    participants: list[str]  # People involved in the meeting
    duration_minutes: int | None  # Estimated meeting duration if mentioned


def classify_email(subject: str, body: str, sender: str) -> ClassificationResult:
    """Classify whether an email is about scheduling a meeting.

    Uses Claude to analyze the email content and determine if the sender
    is asking the user to schedule something.

    Args:
        subject: Email subject line.
        body: Email body text.
        sender: Sender's email address.

    Returns:
        ClassificationResult with the intent and extracted details.
    """
    # TODO: Implement
    # 1. Build a prompt that asks Claude to classify the email
    # 2. Parse the structured response
    # 3. Return a ClassificationResult
    raise NotImplementedError


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
    # TODO: Implement
    # This is the hook classifier — it determines if a new message
    # represents a scheduling commitment that should go on the stash calendar
    raise NotImplementedError
