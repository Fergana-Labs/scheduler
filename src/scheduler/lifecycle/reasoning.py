"""Send a mid-thread reasoning message explaining why a draft was created.

Uses Gmail API insert (not send) so the message appears in the thread
without triggering a notification in the user's Gmail app.
"""

import logging
from datetime import datetime, timedelta

from dateutil import parser as dateutil_parser

from scheduler.calendar.client import CalendarClient
from scheduler.classifier.intent import ClassificationResult
from scheduler.config import config
from scheduler.gmail.client import GmailClient

logger = logging.getLogger(__name__)

REASONING_FROM = "Scheduled <scheduled@ferganalabs.com>"


def _parse_dates(proposed_times: list[str]) -> list[datetime]:
    """Extract unique dates from proposed_times strings, falling back to today."""
    dates: list[datetime] = []
    for text in proposed_times:
        try:
            dt = dateutil_parser.parse(text, fuzzy=True)
            dates.append(dt)
        except (ValueError, OverflowError):
            continue
    if not dates:
        dates.append(datetime.now())
    return dates


def _format_time(dt: datetime) -> str:
    """Format a datetime as '9:00 AM'."""
    return dt.strftime("%-I:%M %p")


def send_reasoning_email(
    user_email: str,
    thread_id: str,
    subject: str,
    classification: ClassificationResult,
    gmail: GmailClient,
    calendar: CalendarClient,
    invite_proposal: dict | None = None,
) -> None:
    """Insert a reasoning message into the thread (no notification)."""
    # Determine relevant dates from proposed_times
    dates = _parse_dates(classification.proposed_times)
    day_start = min(dates).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = max(dates).replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(seconds=1)

    # Fetch calendar events for those days
    events = calendar.get_all_events(day_start, day_end, include_primary=True)

    # Build the email body
    date_label = day_start.strftime("%B %-d, %Y")
    if day_start.date() != (day_end - timedelta(seconds=1)).date():
        date_label = f"{day_start.strftime('%B %-d')} – {(day_end - timedelta(seconds=1)).strftime('%B %-d, %Y')}"

    if events:
        events_lines = "\n".join(
            f"  - {_format_time(ev.start)} – {_format_time(ev.end)}: {ev.summary}"
            for ev in sorted(events, key=lambda e: e.start)
        )
    else:
        events_lines = "  No other meetings"

    invite_section = ""
    if invite_proposal:
        start_str = invite_proposal.get("event_start", "")
        end_str = invite_proposal.get("event_end", "")
        try:
            start_dt = dateutil_parser.parse(start_str)
            end_dt = dateutil_parser.parse(end_str)
            time_label = f"{_format_time(start_dt)} – {_format_time(end_dt)} on {start_dt.strftime('%B %-d')}"
        except (ValueError, OverflowError):
            time_label = f"{start_str} – {end_str}"
        meet_line = " (with Google Meet)" if invite_proposal.get("add_google_meet") else ""
        attendees = invite_proposal.get("attendee_emails", [])
        attendees_label = ", ".join(attendees) or "(none)"
        location = invite_proposal.get("location", "")
        location_line = f"  - Where: {location}\n" if location else ""
        invite_section = (
            f"\n"
            f"Calendar invite:\n"
            f"  When you send this draft, Scheduled will create a calendar invite:\n"
            f"  - What: {invite_proposal.get('event_summary', '')}\n"
            f"  - With: {attendees_label}\n"
            f"  - When: {time_label}{meet_line}\n"
            f"{location_line}"
            f"  An agent will verify your sent message still confirms the meeting\n"
            f"  before sending the invite.\n"
        )

    body = (
        f"Scheduled drafted a reply in this thread.\n"
        f"\n"
        f"Why: {classification.summary}\n"
        f"\n"
        f"Your meetings on {date_label}:\n"
        f"{events_lines}\n"
        f"{invite_section}"
        f"\n"
        f"— Scheduled"
    )

    # Insert directly into Gmail — no notification triggered
    msg_id = gmail.insert_message(
        thread_id=thread_id,
        to=user_email,
        from_addr=REASONING_FROM,
        subject=subject,
        body=body,
    )
    logger.info("reasoning: inserted reasoning message %s in thread %s", msg_id, thread_id)
