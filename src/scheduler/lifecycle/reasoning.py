"""Send a mid-thread reasoning message explaining why a draft was created.

Sends via Postmark so no additional Gmail OAuth scopes are needed.
The message arrives as a normal email from Scheduled to the user.
"""

import logging
from datetime import datetime, timedelta

import httpx
from dateutil import parser as dateutil_parser

from scheduler.calendar.client import CalendarClient
from scheduler.classifier.intent import ClassificationResult
from scheduler.config import config
from scheduler.gmail.client import GmailClient

logger = logging.getLogger(__name__)

POSTMARK_SEND_URL = "https://api.postmarkapp.com/email"
REASONING_FROM = "Scheduled <internal@tryscheduled.com>"


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


def build_reasoning_body(
    classification: ClassificationResult,
    events: list,
    invite_proposal: dict | None = None,
) -> str:
    """Build the reasoning email body. Pure function — no API calls.

    Args:
        classification: The classifier result for this thread.
        events: Calendar events for the relevant date range. Each event
            must have .start (datetime), .end (datetime), .summary (str).
        invite_proposal: Optional dict with pending invite details to show.
    """
    dates = _parse_dates(classification.proposed_times)
    day_start = min(dates).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = max(dates).replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(seconds=1)

    spans_multiple_days = day_start.date() != (day_end - timedelta(seconds=1)).date()

    if spans_multiple_days:
        date_label = f"{day_start.strftime('%B %-d')} – {(day_end - timedelta(seconds=1)).strftime('%B %-d, %Y')}"
    else:
        date_label = day_start.strftime("%B %-d, %Y")

    if events:
        sorted_events = sorted(events, key=lambda e: e.start)
        lines = []
        current_day = None
        for ev in sorted_events:
            if spans_multiple_days and ev.start.date() != current_day:
                current_day = ev.start.date()
                lines.append(f"  {ev.start.strftime('%A, %B %-d')}:")
            lines.append(
                f"  - {_format_time(ev.start)} – {_format_time(ev.end)}: {ev.summary}"
            )
        events_lines = "\n".join(lines)
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

    return (
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


def send_reasoning_email(
    user_email: str,
    thread_id: str,
    subject: str,
    classification: ClassificationResult,
    calendar: CalendarClient,
    gmail: GmailClient,
    invite_proposal: dict | None = None,
) -> None:
    """Send a reasoning message to the user via Postmark."""
    if not config.postmark_server_token:
        logger.info("reasoning: no POSTMARK_SERVER_TOKEN, skipping")
        return

    # Get Message-Id header of the last message in the thread for threading
    message_id_header = ""
    try:
        thread = gmail.get_thread(thread_id)
        if thread:
            message_id_header = thread[-1].headers.get("message-id", "")
    except Exception:
        logger.warning("reasoning: failed to fetch thread %s for threading headers", thread_id)

    dates = _parse_dates(classification.proposed_times)
    day_start = min(dates).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = max(dates).replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(seconds=1)

    events = calendar.get_all_events(day_start, day_end, include_primary=True)
    body = build_reasoning_body(classification, events, invite_proposal=invite_proposal)

    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    payload: dict = {
        "From": REASONING_FROM,
        "To": user_email,
        "Subject": reply_subject,
        "TextBody": body,
    }
    if message_id_header:
        payload["Headers"] = [
            {"Name": "In-Reply-To", "Value": message_id_header},
            {"Name": "References", "Value": message_id_header},
        ]

    resp = httpx.post(
        POSTMARK_SEND_URL,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": config.postmark_server_token,
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    logger.info("reasoning: sent reasoning email to %s for thread %s", user_email, thread_id)
