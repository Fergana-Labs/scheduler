"""Message hook — classifies new messages and updates the stash calendar.

Runs on every new incoming message (email, text, Slack) to determine:
1. Is this message about scheduling?
2. If so, does it create a new event or modify an existing one?
3. Update the stash calendar accordingly.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from scheduler.auth.google_auth import get_credentials
from scheduler.calendar.client import CalendarClient, Event
from scheduler.classifier.intent import classify_message_for_event


def _get_calendar_client() -> CalendarClient:
    """Helper to construct a CalendarClient from stored credentials."""
    creds = get_credentials()
    # Use default stash calendar name; CalendarClient will create if missing.
    return CalendarClient(creds)


def process_new_message(message: str, sender: str, source: str = "email") -> bool:
    """Process a new message through the scheduling hook.

    Args:
        message: The message text.
        sender: Who sent it.
        source: Where it came from (email, text, slack, etc.).

    Returns:
        True if a stash calendar event was created/updated.
    """
    event_data = classify_message_for_event(message, sender)
    if event_data is None:
        return False

    summary = event_data["summary"]
    start_iso = event_data["start_iso"]
    duration_minutes = event_data["duration_minutes"]

    try:
        start = datetime.fromisoformat(start_iso)
    except ValueError:
        return False

    end = start + timedelta(minutes=duration_minutes)

    calendar = _get_calendar_client()

    # Simple deduplication: look for an existing stash event with a matching
    # summary in a small window around the proposed time.
    window_start = start - timedelta(minutes=15)
    window_end = end + timedelta(minutes=15)
    existing = calendar.find_event(summary=summary, time_min=window_start, time_max=window_end)

    description_lines = [
        f"[source: {source}]",
        f"Detected from message by {sender}.",
    ]
    description = "\n".join(description_lines)

    event = Event(
        id=None,
        summary=summary,
        start=start,
        end=end,
        description=description,
        source=source,
    )

    if existing is not None and existing.id:
        calendar.update_event(existing.id, event)
    else:
        calendar.add_event(event)

    return True


def process_email_by_id(message_id: str) -> bool:
    """Process a specific email by Gmail message ID."""
    from scheduler.gmail.client import GmailClient

    creds = get_credentials()
    gmail = GmailClient(creds)
    email = gmail.get_email(message_id)

    # Use the email body as the message text; treat the sender as the
    # calendar event counterparty.
    return process_new_message(email.body, email.sender, source="email")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a message through the scheduling hook")
    parser.add_argument("--message-id", help="Gmail message ID to process")
    parser.add_argument("--text", help="Raw message text to process")
    parser.add_argument("--sender", help="Sender of the message", default="unknown")
    parser.add_argument("--source", help="Source of the message", default="email")
    args = parser.parse_args()

    if args.message_id:
        process_email_by_id(args.message_id)
    elif args.text:
        process_new_message(args.text, args.sender, args.source)
    else:
        parser.print_help()
