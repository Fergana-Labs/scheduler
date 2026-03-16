"""Message hook — classifies new messages and updates the stash calendar.

Runs on every new incoming message (email, text, Slack) to determine:
1. Is this message about scheduling?
2. If so, does it create a new event or modify an existing one?
3. Update the stash calendar accordingly.
"""

import argparse

from scheduler.auth.google_auth import get_credentials
from scheduler.calendar.client import CalendarClient
from scheduler.classifier.intent import classify_message_for_event
from scheduler.config import config


def process_new_message(message: str, sender: str, source: str = "email") -> bool:
    """Process a new message through the scheduling hook.

    Args:
        message: The message text.
        sender: Who sent it.
        source: Where it came from (email, text, slack, etc.).

    Returns:
        True if a stash calendar event was created/updated.
    """
    # TODO: Implement
    # 1. Classify the message
    # 2. If it's a scheduling message, extract event details
    # 3. Check for existing events to avoid duplicates
    # 4. Create or update the stash calendar event
    raise NotImplementedError


def process_email_by_id(message_id: str) -> bool:
    """Process a specific email by Gmail message ID."""
    # TODO: Implement
    # 1. Fetch the email via GmailClient
    # 2. Call process_new_message with the email body
    raise NotImplementedError


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
