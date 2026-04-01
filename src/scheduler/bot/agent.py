"""Bot reply agent — reads thread, checks calendar, replies from bot account.

Unlike the draft composer (which creates drafts in the user's Gmail), this agent
sends replies directly from the bot's Gmail account (scheduling@tryscheduled.com).
It acts as a visible third-party scheduling assistant.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

from scheduler.bot.conversation import (
    build_conversation_context,
    record_bot_reply,
    transition,
)
from scheduler.bot.gmail import bot_email_address, get_bot_gmail_client
from scheduler.config import config
from scheduler.db import BotConversationRow, UserRow

if TYPE_CHECKING:
    from scheduler.calendar.client import CalendarClient
    from scheduler.gmail.client import GmailClient

logger = logging.getLogger(__name__)


def _build_system_prompt(user: UserRow, conversation: BotConversationRow) -> str:
    """Build the system prompt for the bot reply agent."""
    display_name = user.display_name or user.email.split("@")[0]

    parts = [
        f"You are Scheduled, a scheduling assistant acting on behalf of "
        f"{display_name} ({user.google_email or user.email}).\n\n"
        f"You communicate directly with the people {display_name} is scheduling "
        f"with. You are a polite, professional third-party assistant — you are NOT "
        f"pretending to be {display_name}. Always make it clear you are their "
        f"scheduling assistant.\n\n"
        f"Your email address is {bot_email_address()}. All replies you send come "
        f"from this address.",
    ]

    # Load scheduling preferences guide if available
    from scheduler.guides import load_guide

    prefs = load_guide("scheduling_preferences", user_id=str(user.id))
    if prefs:
        parts.append(
            "\n\n## Scheduling Preferences\n"
            f"Use these patterns when proposing times for {display_name}:\n\n"
            + prefs
        )
    else:
        from scheduler.guides.defaults import DEFAULT_SCHEDULING_PREFERENCES

        parts.append(
            "\n\n## Scheduling Preferences\n"
            + DEFAULT_SCHEDULING_PREFERENCES
        )

    # Conversation state context
    conv_context = build_conversation_context(conversation)
    if conv_context:
        parts.append(
            "\n\n## Current Conversation State\n"
            + conv_context
        )

    parts.append(
        "\n\n## Rules\n"
        "- Always identify yourself in your first reply: "
        f"\"Hi, I'm Scheduled, {display_name}'s scheduling assistant.\"\n"
        "- On follow-up replies in the same thread, skip the introduction.\n"
        "- Be warm, concise, and helpful.\n"
        "- Never re-suggest times that were already declined.\n"
        "- If the counterparty proposes times, cross-check with the user's calendar.\n"
        "- When a time is confirmed by both parties, create a calendar invite.\n"
        f"- If you're unsure what {display_name} wants, use the escalate tool to ask them.\n"
        "- Do NOT escalate just because the conversation is long — that's where you're most useful.\n"
        "- Only escalate for genuinely ambiguous situations the user needs to weigh in on.\n"
        f"- Keep {display_name} in CC on all replies so they see the conversation.\n"
        "- Always include a scheduling link in your first proposal email.\n"
    )

    return "\n".join(parts)


def _build_tools(
    bot_gmail: GmailClient,
    user_calendar: CalendarClient,
    bot_calendar: CalendarClient,
    user: UserRow,
    conversation: BotConversationRow,
):
    """Build the agent tools for the bot reply agent."""

    reply_result: dict = {"sent": False, "message_id": None}
    invite_result: dict = {"created": False, "event_id": None}
    proposed_windows_collector: list[dict] = []

    user_email = user.google_email or user.email
    display_name = user.display_name or user.email.split("@")[0]

    @tool(
        "read_thread",
        "Read the full email thread from the bot's inbox to understand the context.",
        {"thread_id": str},
    )
    async def read_thread(args):
        thread = bot_gmail.get_thread(args["thread_id"])
        messages = [
            {
                "sender": m.sender,
                "recipient": m.recipient,
                "cc": m.cc,
                "subject": m.subject,
                "body": m.body,
                "date": m.date.isoformat(),
            }
            for m in thread
        ]
        return {"content": [{"type": "text", "text": json.dumps(messages)}]}

    @tool(
        "get_calendar_events",
        f"Check {display_name}'s calendar for availability in a date range. "
        "Returns all existing events so you can find free slots.",
        {"start_date": str, "end_date": str},
    )
    async def get_calendar_events(args):
        start = datetime.fromisoformat(args["start_date"])
        end = datetime.fromisoformat(args["end_date"])
        events = user_calendar.get_all_events(start, end, include_primary=True)
        payload = [
            {
                "summary": e.summary,
                "start": e.start.isoformat(),
                "end": e.end.isoformat(),
                "response_status": e.response_status,
            }
            for e in events
        ]
        return {"content": [{"type": "text", "text": json.dumps(payload)}]}

    @tool(
        "send_reply",
        "Send a reply in the thread from the bot's email address. "
        f"Always include {user_email} in the CC so they see the conversation. "
        "Call this exactly once per turn.",
        {"thread_id": str, "to": str, "cc": str, "subject": str, "body": str},
    )
    async def send_reply(args):
        # Ensure user is in CC
        cc = args.get("cc", "")
        cc_addrs = [a.strip() for a in cc.split(",") if a.strip()]
        if user_email.lower() not in [a.lower() for a in cc_addrs]:
            cc_addrs.append(user_email)
        # Remove bot's own address from CC
        bot_addr = bot_email_address().lower()
        cc_addrs = [a for a in cc_addrs if a.lower() != bot_addr]

        message_id = bot_gmail.send_email(
            thread_id=args["thread_id"],
            to=args["to"],
            subject=args["subject"],
            body=args["body"],
            cc=", ".join(cc_addrs),
        )
        reply_result["sent"] = True
        reply_result["message_id"] = message_id
        return {"content": [{"type": "text", "text": json.dumps({"status": "sent", "message_id": message_id})}]}

    @tool(
        "create_calendar_invite",
        "Create a calendar event and send invites to all participants. "
        "Use this when a meeting time has been confirmed by both parties. "
        f"The invite is created on the bot's calendar and sent to {display_name} "
        "and the counterparty as attendees (like Calendly).",
        {
            "summary": str,
            "start": str,
            "end": str,
            "attendee_emails": list[str],
            "location": str,
            "add_google_meet": bool,
        },
    )
    async def create_calendar_invite(args):
        attendees = args["attendee_emails"]
        # Always include the user
        if user_email.lower() not in [a.lower() for a in attendees]:
            attendees.append(user_email)

        event_id = bot_calendar.create_invite_event(
            summary=args["summary"],
            start=datetime.fromisoformat(args["start"]),
            end=datetime.fromisoformat(args["end"]),
            attendee_emails=attendees,
            location=args.get("location", ""),
            add_google_meet=args.get("add_google_meet", False),
        )
        invite_result["created"] = True
        invite_result["event_id"] = event_id
        return {"content": [{"type": "text", "text": json.dumps({"status": "invite_sent", "event_id": event_id})}]}

    @tool(
        "record_proposed_times",
        "Record the specific time windows you're about to propose in your reply. "
        "Call this BEFORE send_reply so the system can track what was proposed. "
        "Each window should have date (YYYY-MM-DD), start (HH:MM), end (HH:MM).",
        {"windows": list[dict]},
    )
    async def record_proposed_times(args):
        proposed_windows_collector.extend(args["windows"])
        return {"content": [{"type": "text", "text": json.dumps({"status": "recorded", "count": len(args["windows"])})}]}

    @tool(
        "escalate_to_user",
        f"Send a private email to {display_name} asking for guidance. "
        "ONLY use this when you genuinely don't know how to proceed — "
        "NOT for long conversations or routine counterproposals.",
        {"question": str, "thread_summary": str},
    )
    async def escalate_to_user(args):
        import base64
        from email.mime.text import MIMEText

        subject = "[Scheduled] Need your input on scheduling"
        body = (
            f"Hi {display_name},\n\n"
            f"I'm handling a scheduling thread and need your input:\n\n"
            f"Thread summary: {args['thread_summary']}\n\n"
            f"My question: {args['question']}\n\n"
            f"You can reply to the original thread directly to take over, "
            f"or reply to this email and I'll incorporate your answer.\n\n"
            f"— Scheduled"
        )

        mime_msg = MIMEText(body)
        mime_msg["To"] = user_email
        mime_msg["Subject"] = subject

        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("ascii")
        service = bot_gmail._get_service()
        sent = service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        return {"content": [{"type": "text", "text": json.dumps({"status": "escalated", "message_id": sent["id"]})}]}

    all_tools = [
        read_thread, get_calendar_events, send_reply,
        create_calendar_invite, record_proposed_times, escalate_to_user,
    ]

    return all_tools, reply_result, invite_result, proposed_windows_collector


def compose_and_send(
    user: UserRow,
    conversation: BotConversationRow,
    email,
    user_calendar: CalendarClient,
) -> dict:
    """Run the bot reply agent for one turn of a conversation.

    Args:
        user: The registered Scheduled user.
        conversation: The bot conversation state.
        email: The triggering email from the bot's inbox.
        user_calendar: Calendar client with the user's credentials.

    Returns:
        Dict with 'sent' (bool), 'message_id', 'invite_created', 'event_id'.
    """
    bot_gmail = get_bot_gmail_client()

    # Build a CalendarClient for the bot's own account (for creating invite events)
    from scheduler.bot.gmail import _build_bot_credentials
    from scheduler.calendar.client import CalendarClient as CalClient

    bot_creds = _build_bot_credentials()
    bot_calendar = CalClient(bot_creds, "Bot Calendar")

    system_prompt = _build_system_prompt(user, conversation)
    tools, reply_result, invite_result, proposed_windows = _build_tools(
        bot_gmail, user_calendar, bot_calendar, user, conversation,
    )
    server = create_sdk_mcp_server("bot-tools", tools=tools)

    user_tz = user_calendar.get_user_timezone()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    prompt = (
        f"The current date and time is {now}.\n"
        f"The user's timezone is {user_tz}.\n\n"
        f"A new email arrived in this scheduling thread. Here's the triggering message:\n\n"
        f"Thread ID: {email.thread_id}\n"
        f"From: {email.sender}\n"
        f"To: {email.recipient}\n"
        f"CC: {email.cc}\n"
        f"Subject: {email.subject}\n"
        f"Snippet: {email.snippet}\n\n"
        f"Your job:\n"
        f"1. Read the full thread using read_thread to understand the context.\n"
        f"2. Check the user's calendar for availability (next 14 days).\n"
        f"3. Decide what to do:\n"
        f"   - If this is the first message: propose times that work for the user.\n"
        f"   - If the counterparty declined previous times: propose NEW times.\n"
        f"   - If the counterparty proposed times: check calendar and accept/decline.\n"
        f"   - If a time is confirmed: create a calendar invite and send confirmation.\n"
        f"   - If the user replied in the thread: step back, don't send anything.\n"
        f"4. Before sending a reply with proposed times, call record_proposed_times.\n"
        f"5. Send your reply using send_reply (exactly once).\n"
        f"6. If a time is confirmed, call create_calendar_invite.\n\n"
        f"If the thread is already resolved (time confirmed, invite sent), "
        f"do NOT send another reply — just stop.\n"
    )

    options = ClaudeAgentOptions(
        mcp_servers={"bot": server},
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",
        model="claude-sonnet-4-6",
    )

    os.environ.pop("CLAUDECODE", None)

    async def _run():
        client = ClaudeSDKClient(options=options)
        await client.connect()
        try:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            logger.info("bot_agent: %s", block.text)
                elif isinstance(message, ResultMessage):
                    logger.info("bot_agent result: %s", message.result)
        finally:
            await client.disconnect()

    try:
        asyncio.run(_run())
    finally:
        bot_calendar.close()

    # Update conversation state based on what the agent did
    if reply_result["sent"]:
        record_bot_reply(conversation, proposed_windows=proposed_windows or None)
        if proposed_windows and conversation.state in ("new", "negotiating"):
            transition(conversation, "proposing")

    if invite_result["created"]:
        transition(conversation, "confirmed")
        transition(conversation, "done")

    return {
        "sent": reply_result["sent"],
        "message_id": reply_result["message_id"],
        "invite_created": invite_result["created"],
        "event_id": invite_result["event_id"],
    }
