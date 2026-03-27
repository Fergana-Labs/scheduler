"""Lifecycle welcome email: send a personalized Postmark email, then create an example draft reply."""

import json
import logging
import time
from datetime import datetime, timedelta

import httpx
from anthropic import Anthropic

from scheduler.auth.google_auth import load_credentials
from scheduler.calendar.client import CalendarClient
from scheduler.config import config
from scheduler.db import get_user_by_id
from scheduler.gmail.client import GmailClient
from scheduler.guides import load_guide
from scheduler.guides.defaults import DEFAULT_EMAIL_STYLE, DEFAULT_SCHEDULING_PREFERENCES

logger = logging.getLogger(__name__)

POSTMARK_SEND_URL = "https://api.postmarkapp.com/email"


def _get_anthropic_client() -> Anthropic:
    if not config.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return Anthropic(api_key=config.anthropic_api_key)


def _extract_text(response) -> str:
    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def generate_welcome_email(
    user_email: str,
    scheduling_prefs: str,
    email_style: str,
    client: Anthropic | None = None,
) -> dict:
    """Generate a welcome email. Pure generation — no side effects.

    Returns {"subject": "...", "body": "..."}.
    """
    if client is None:
        client = _get_anthropic_client()

    welcome_system = (
        "You are writing a warm, personalized welcome email from Sam at Scheduled "
        "(sam@tryscheduled.com) to a new user. The email should suggest hopping on a "
        "quick chat to help them get the most out of Scheduled.\n\n"
        "You have the user's scheduling preferences and email style guides below. "
        "Reference specific details from their scheduling patterns to show the email "
        "is personal — for example, mention their preferred meeting times, typical "
        "meeting lengths, or communication style.\n\n"
        "Keep it brief, friendly, and genuine — like a real person wrote it, not a template.\n\n"
        f"## User's Scheduling Preferences\n{scheduling_prefs}\n\n"
        f"## User's Email Style\n{email_style}\n\n"
        "Respond with a JSON object only:\n"
        '{"subject": "...", "body": "..."}\n'
        "The body should be plain text (no HTML). Sign off as Sam."
    )

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0.7,
        system=welcome_system,
        messages=[
            {
                "role": "user",
                "content": f"Write a welcome email to {user_email}.",
            }
        ],
    )
    return json.loads(_extract_text(resp))


def generate_draft_reply(
    sender: str,
    subject: str,
    welcome_body: str,
    email_style: str,
    scheduling_prefs: str,
    events_text: str,
    client: Anthropic | None = None,
) -> str:
    """Generate an example draft reply to the welcome email. Pure generation — no side effects.

    Returns the draft body as plain text.
    """
    if client is None:
        client = _get_anthropic_client()

    draft_system = (
        "You are composing a draft email reply on behalf of a user. The reply should be "
        "written in the user's own writing style (see their email style guide below) and "
        "propose a specific free time for a chat based on their calendar and preferences.\n\n"
        "The draft MUST start with this disclaimer on its own line:\n"
        "[This is an example draft created by Scheduled to show how it works — feel free to edit or delete it]\n\n"
        "After the disclaimer, write the actual reply. Keep it natural and brief — "
        "match the user's tone and style exactly.\n\n"
        f"## User's Email Style\n{email_style}\n\n"
        f"## User's Scheduling Preferences\n{scheduling_prefs}\n\n"
        f"## Calendar (next 14 days)\n{events_text}\n\n"
        "Respond with the plain text body only (no JSON, no subject line). "
        "The reply should propose a specific date and time that is free on the calendar."
    )

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0.7,
        system=draft_system,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Compose a reply to this email:\n\n"
                    f"From: {sender}\n"
                    f"Subject: {subject}\n\n"
                    f"{welcome_body}"
                ),
            }
        ],
    )
    return _extract_text(resp)


def send_lifecycle_email(user_id: str) -> None:
    """Send a personalized welcome email and create an example draft reply.

    Steps:
    1. Load user info and guides
    2. Generate welcome email via Anthropic
    3. Send via Postmark
    4. Poll Gmail for the arriving email
    5. Fetch calendar availability
    6. Generate example draft reply via Anthropic
    7. Create draft in Gmail
    """
    # (a) Load user + guides
    user = get_user_by_id(user_id)
    if not user:
        logger.warning("lifecycle: user not found user_id=%s", user_id)
        return

    scheduling_prefs = load_guide("scheduling_preferences", user_id)
    email_style = load_guide("email_style", user_id)

    if not scheduling_prefs:
        logger.info(
            "lifecycle: no scheduling_preferences for user=%s, using default", user_id
        )
        scheduling_prefs = DEFAULT_SCHEDULING_PREFERENCES

    if not email_style:
        logger.info(
            "lifecycle: no email_style guide for user=%s, using default", user_id
        )
        email_style = DEFAULT_EMAIL_STYLE

    # (b) Generate welcome email via Anthropic
    client = _get_anthropic_client()

    try:
        welcome_data = generate_welcome_email(user.email, scheduling_prefs, email_style, client)
        subject = welcome_data["subject"]
        welcome_body = welcome_data["body"]
    except Exception:
        logger.exception("lifecycle: failed to generate welcome email for user=%s", user_id)
        return

    # (c) Send via Postmark
    if not config.postmark_server_token:
        logger.info("lifecycle: no POSTMARK_SERVER_TOKEN, skipping send for user=%s", user_id)
        return

    try:
        pm_resp = httpx.post(
            POSTMARK_SEND_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": config.postmark_server_token,
            },
            json={
                "From": config.postmark_from_email,
                "To": user.email,
                "Subject": subject,
                "TextBody": welcome_body,
            },
            timeout=15,
        )
        pm_resp.raise_for_status()
        logger.info("lifecycle: welcome email sent to %s (subject=%r)", user.email, subject)
    except Exception:
        logger.exception("lifecycle: failed to send Postmark email for user=%s", user_id)
        return

    # (d) Poll Gmail for the arriving email
    creds = load_credentials(user_id)
    gmail = GmailClient(creds)

    sender = config.postmark_from_email
    search_query = f"from:{sender} subject:\"{subject}\" newer_than:1d"
    thread_id = None
    delays = [2, 4, 6, 8, 10]

    for attempt, delay in enumerate(delays, 1):
        time.sleep(delay)
        try:
            results = gmail.search(search_query, max_results=1)
            if results:
                thread_id = results[0].thread_id
                logger.info(
                    "lifecycle: found welcome email in Gmail (attempt %d) thread=%s",
                    attempt,
                    thread_id,
                )
                break
        except Exception:
            logger.warning("lifecycle: Gmail search attempt %d failed", attempt, exc_info=True)

    if not thread_id:
        logger.warning("lifecycle: timed out polling for welcome email for user=%s", user_id)
        return

    # (e) Fetch calendar availability
    calendar = CalendarClient(creds, config.scheduled_calendar_name)
    now = datetime.now()
    events = calendar.get_all_events(now, now + timedelta(days=14))

    events_text = "No events in the next 14 days." if not events else ""
    for ev in events:
        events_text += f"- {ev.summary}: {ev.start.strftime('%a %b %d, %I:%M %p')} – {ev.end.strftime('%I:%M %p')}\n"

    # (f) Generate example draft reply
    try:
        draft_body = generate_draft_reply(
            sender, subject, welcome_body,
            email_style, scheduling_prefs, events_text, client,
        )
    except Exception:
        logger.exception("lifecycle: failed to generate draft reply for user=%s", user_id)
        return

    # (g) Create draft in Gmail
    try:
        reply_subject = f"Re: {subject}" if not subject.startswith("Re:") else subject
        draft_id = gmail.create_draft(
            thread_id=thread_id,
            to=sender,
            subject=reply_subject,
            body=draft_body,
        )
        logger.info("lifecycle: created example draft for user=%s draft_id=%s", user_id, draft_id)
    except Exception:
        logger.exception("lifecycle: failed to create draft for user=%s", user_id)
