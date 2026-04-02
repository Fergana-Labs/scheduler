"""Lifecycle welcome email: send a personalized Postmark email, then create an example draft reply."""

import html as html_mod
import logging
import time
from datetime import datetime, timedelta

import httpx
from anthropic import Anthropic

from scheduler.auth.google_auth import load_credentials
from scheduler.calendar.client import CalendarClient
from scheduler.classifier.intent import ClassificationResult, SchedulingIntent
from scheduler.config import config
from scheduler.db import create_scheduling_link, get_user_by_id
from scheduler.drafts.composer import _apply_footer
from scheduler.gmail.client import GmailClient
from scheduler.guides import load_guide
from scheduler.guides.defaults import DEFAULT_EMAIL_STYLE, DEFAULT_SCHEDULING_PREFERENCES
from scheduler.lifecycle.reasoning import send_reasoning_email

logger = logging.getLogger(__name__)

POSTMARK_SEND_URL = "https://api.postmarkapp.com/email"

WELCOME_SUBJECT = "Welcome to Scheduled!"

WELCOME_TEMPLATE = """\
<p>Hello and welcome to Scheduled!</p>

<p>We're excited you are here! Our goal is to empower you to focus on what matters \
by automating away the mind-numbing tasks that have become our lives. We image a world \
where humans don't have to spend another minute doing such mundane tasks (trust us, one \
of us used to be a management consultant, so we've had our fair share of sleep-less nights \
aligning boxes and scheduling meetings).</p>

<p>Unlike other scheduling tools like Calendly, Cal&#46;com, or Fxyer, our product \
philosophy is built around seamlessly fitting into your existing scheduling preferences \
and workflow. If you head over to <a href="https://tryscheduled.com/settings">your settings</a>, \
you will find guides based on what we have learned from how you have scheduled in the past. \
These will be used by our agent to help you schedule future meetings.</p>

<p>Note that we take privacy very seriously and this is the only personal data of yours \
we store on our server, which can be verified by looking through our open source codebase.</p>

<p>{personalized_snippet}</p>

<p>You are all set for now. Expect to see drafts written by our agent pop-up automatically \
in threads where scheduling is a concern. We handle all of the background work of checking \
against your calendar, preferences, and sending invites for you. Feel free to edit these \
drafts or just send as is.</p>

<p>If this resonates, we would love to hop on a quick 15 minute call to get you up to speed \
and to see how else we can build this to match your needs. Just reply to the email (there \
should be a draft auto-populated below) and we'll use scheduled to automatically find a time.</p>

<p>Warmly,</p>

<p>Sam<br>CEO and Co-Founder of \
<a href="https://tryscheduled.com">Scheduled</a> by \
<a href="https://ferganalabs.com">Fergana Labs</a></p>"""


BOT_WELCOME_TEMPLATE = """\
<p>Hello and welcome to Scheduled!</p>

<p>We're excited you are here! Our goal is to empower you to focus on what matters \
by automating away the mind-numbing tasks that have become our lives.</p>

<p>Unlike scheduling link tools like Calendly or Cal&#46;com, Scheduled is a scheduling \
assistant that works inside your email conversations. Just CC \
<strong>scheduling@tryscheduled.com</strong> on any email thread where you need to find \
a time, and your assistant will take it from there — checking your calendar, proposing \
times, and handling the back-and-forth until a meeting is booked.</p>

<p>If you head over to <a href="https://tryscheduled.com/settings">your settings</a>, \
you will find a guide based on your scheduling preferences. Your assistant uses this to \
understand when and how you like to meet.</p>

<p>{personalized_snippet}</p>

<p>You're all set! To try it out, just CC <strong>scheduling@tryscheduled.com</strong> \
on your next scheduling email — or reply to this email and we'll use Scheduled to \
automatically find a time for a quick welcome call.</p>

<p>Warmly,</p>

<p>Sam<br>CEO and Co-Founder of \
<a href="https://tryscheduled.com">Scheduled</a> by \
<a href="https://ferganalabs.com">Fergana Labs</a></p>"""


def _get_anthropic_client() -> Anthropic:
    from scheduler.classifier.intent import _get_anthropic_client as _shared
    return _shared()


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
    has_real_guides: bool = True,
) -> dict:
    """Generate a welcome email using a fixed template with a personalized snippet.

    Returns {"subject": "...", "body": "..."}.
    """
    if has_real_guides:
        if client is None:
            client = _get_anthropic_client()

        snippet_system = (
            "You are writing 1-2 personalized sentences for a welcome email from Sam at Scheduled. "
            "These sentences will be inserted into a template email to make it feel personal.\n\n"
            "The perspective should be from 'we' (the Scheduled team) observing the user's "
            "scheduling patterns — e.g., 'We see you tend to do XYZ meetings when XYZ' or similar.\n\n"
            "You have the user's scheduling preferences below. Use them to write the snippet, "
            "but follow these privacy rules strictly:\n"
            "- Never reference specific meeting names, attendee names, or calendar details.\n"
            "- You can mention general scheduling patterns (e.g., 'We noticed you tend to keep "
            "meetings short and prefer afternoons') but never specific events or people.\n"
            "- A stranger reading these sentences should learn nothing about the user's "
            "specific calendar, contacts, or habits.\n\n"
            f"## User's Scheduling Preferences\n{scheduling_prefs}\n\n"
            "Respond with ONLY the 1-2 sentences, nothing else. No quotes, no JSON, no preamble."
        )

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            temperature=0.7,
            system=snippet_system,
            messages=[
                {
                    "role": "user",
                    "content": f"Write a personalized snippet for {user_email}.",
                }
            ],
        )
        snippet = _extract_text(resp)
    else:
        snippet = "We'll learn your scheduling preferences over time as you use Scheduled."

    body = WELCOME_TEMPLATE.format(personalized_snippet=html_mod.escape(snippet))
    return {"subject": WELCOME_SUBJECT, "body": body}


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
        "Privacy rules:\n"
        "- Never reference specific meeting names, attendee names, or calendar details.\n"
        "- You may propose a specific time, but never explain WHY that time is free.\n"
        "- You can mention general preferences (eg you like to keep your mornings clear on friday) but not specific events (eg DO NOT say you like to go to pilates on friday mornings)\n"
        "- A stranger reading this draft should learn nothing about the user's "
        "calendar, contacts, or habits.\n\n"
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
    """Send a welcome email, create an example draft reply with scheduling link, and send a reasoning email.

    Steps:
    1. Load user info and guides
    2. Generate personalized snippet and assemble welcome email from template
    3. Send via Postmark
    4. Poll Gmail for the arriving email
    5. Fetch calendar availability
    6. Generate example draft reply via Anthropic
    7. Create scheduling link and apply footer to draft
    8. Create draft in Gmail
    9. Send example reasoning email in the thread
    """
    # (a) Load user + guides
    user = get_user_by_id(user_id)
    if not user:
        logger.warning("lifecycle: user not found user_id=%s", user_id)
        return

    scheduling_prefs = load_guide("scheduling_preferences", user_id)
    email_style = load_guide("email_style", user_id)
    has_real_guides = bool(scheduling_prefs and email_style)

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
        welcome_data = generate_welcome_email(
            user.email, scheduling_prefs, email_style, client,
            has_real_guides=has_real_guides,
        )
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
                "HtmlBody": welcome_body,
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
        gmail.close()
        return

    # (e) Fetch calendar availability
    calendar = CalendarClient(creds, config.scheduled_calendar_name, scheduled_calendar_id=user.scheduled_calendar_id)
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

    # (g) Create scheduling link and apply footer to draft
    scheduling_link_url = None
    try:
        user_tz = calendar.get_user_timezone()
        link = create_scheduling_link(
            user_id=user_id,
            attendee_email=sender,
            mode="availability",
            event_summary="Welcome Call",
            duration_minutes=15,
            tz=user_tz,
            thread_id=thread_id,
        )
        scheduling_link_url = f"{config.web_app_url}/schedule/{link.id}"
        logger.info("lifecycle: created scheduling link for user=%s link_id=%s", user_id, link.id)
    except Exception:
        logger.exception("lifecycle: failed to create scheduling link for user=%s", user_id)

    draft_body, content_type = _apply_footer(draft_body, user_id, scheduling_link_url)

    # (h) Create draft in Gmail
    try:
        reply_subject = f"Re: {subject}" if not subject.startswith("Re:") else subject
        draft_id = gmail.create_draft(
            thread_id=thread_id,
            to=sender,
            subject=reply_subject,
            body=draft_body,
            content_type=content_type,
        )
        logger.info("lifecycle: created example draft for user=%s draft_id=%s", user_id, draft_id)
    except Exception:
        logger.exception("lifecycle: failed to create draft for user=%s", user_id)
        return

    # (i) Send example reasoning email
    try:
        tomorrow = now + timedelta(days=1)
        proposed_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        classification = ClassificationResult(
            intent=SchedulingIntent.NEEDS_DRAFT,
            confidence=0.95,
            summary="Schedule a welcome call with Sam from Scheduled",
            proposed_times=[proposed_time.strftime("%B %d, %Y %I:%M %p")],
            participants=[sender],
            duration_minutes=15,
        )
        send_reasoning_email(
            user_email=user.email,
            thread_id=thread_id,
            subject=subject,
            classification=classification,
            calendar=calendar,
            gmail=gmail,
        )
        logger.info("lifecycle: sent example reasoning email for user=%s", user_id)
    except Exception:
        logger.exception("lifecycle: failed to send reasoning email for user=%s", user_id)
    finally:
        gmail.close()
        calendar.close()


def send_bot_lifecycle_email(user_id: str) -> None:
    """Send a welcome email for bot-mode users.

    Simpler than the draft-mode flow — just sends via Postmark with a
    personalized snippet. No Gmail polling, draft creation, or reasoning email.
    """
    user = get_user_by_id(user_id)
    if not user:
        logger.warning("lifecycle_bot: user not found user_id=%s", user_id)
        return

    scheduling_prefs = load_guide("scheduling_preferences", user_id)
    has_real_guides = bool(scheduling_prefs)

    if not scheduling_prefs:
        scheduling_prefs = DEFAULT_SCHEDULING_PREFERENCES

    # Generate personalized snippet
    if has_real_guides:
        try:
            client = _get_anthropic_client()
            snippet_system = (
                "You are writing 1-2 personalized sentences for a welcome email from Sam at Scheduled. "
                "These sentences will be inserted into a template email to make it feel personal.\n\n"
                "The perspective should be from 'we' (the Scheduled team) observing the user's "
                "scheduling patterns — e.g., 'We see you tend to do XYZ meetings when XYZ' or similar.\n\n"
                "You have the user's scheduling preferences below. Use them to write the snippet, "
                "but follow these privacy rules strictly:\n"
                "- Never reference specific meeting names, attendee names, or calendar details.\n"
                "- You can mention general scheduling patterns but never specific events or people.\n"
                "- A stranger reading these sentences should learn nothing about the user's "
                "specific calendar, contacts, or habits.\n\n"
                f"## User's Scheduling Preferences\n{scheduling_prefs}\n\n"
                "Respond with ONLY the 1-2 sentences, nothing else. No quotes, no JSON, no preamble."
            )
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=256,
                temperature=0.7,
                system=snippet_system,
                messages=[{"role": "user", "content": f"Write a personalized snippet for {user.email}."}],
            )
            snippet = _extract_text(resp)
        except Exception:
            logger.exception("lifecycle_bot: failed to generate snippet for user=%s", user_id)
            snippet = "We'll learn your scheduling preferences over time as you use Scheduled."
    else:
        snippet = "We'll learn your scheduling preferences over time as you use Scheduled."

    body = BOT_WELCOME_TEMPLATE.format(personalized_snippet=html_mod.escape(snippet))

    # Send via Postmark
    if not config.postmark_server_token:
        logger.info("lifecycle_bot: no POSTMARK_SERVER_TOKEN, skipping send for user=%s", user_id)
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
                "Subject": WELCOME_SUBJECT,
                "HtmlBody": body,
            },
            timeout=15,
        )
        pm_resp.raise_for_status()
        logger.info("lifecycle_bot: welcome email sent to %s", user.email)
    except Exception:
        logger.exception("lifecycle_bot: failed to send Postmark email for user=%s", user_id)
