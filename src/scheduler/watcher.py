"""Email watcher — polls Gmail for new scheduling emails and creates drafts.

This is the main runtime loop. It periodically checks for new emails,
classifies them for scheduling intent, and creates draft replies with
proposed meeting times.
"""

import time

from scheduler.auth.google_auth import get_credentials
from scheduler.availability.checker import AvailabilityChecker
from scheduler.calendar.client import CalendarClient
from scheduler.classifier.intent import SchedulingIntent, classify_email
from scheduler.config import config
from scheduler.drafts.composer import DraftComposer
from scheduler.gmail.client import GmailClient


def run_watcher():
    """Main watcher loop.

    1. Authenticate with Google
    2. Poll for new emails at the configured interval
    3. For each new email, classify for scheduling intent
    4. If scheduling intent detected, compose and create a draft reply
    """
    # TODO: Implement
    # Pseudocode:
    #
    # creds = get_credentials()
    # gmail = GmailClient(creds)
    # calendar = CalendarClient(creds, config.stash_calendar_name)
    # availability = AvailabilityChecker(calendar)
    # composer = DraftComposer(gmail, availability)
    #
    # last_check = now
    # while True:
    #     emails = gmail.get_recent_emails(since=last_check)
    #     for email in emails:
    #         result = classify_email(email.subject, email.body, email.sender)
    #         if result.intent == SchedulingIntent.REQUESTING_MEETING:
    #             draft_id = composer.compose_and_create_draft(email, result)
    #             print(f"Created draft {draft_id} for thread {email.thread_id}")
    #     last_check = now
    #     sleep(config.watcher_poll_interval)
    raise NotImplementedError


if __name__ == "__main__":
    print("Starting email watcher...")
    run_watcher()
