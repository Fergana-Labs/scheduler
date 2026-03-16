"""Onboarding agent — backfills the stash calendar from Gmail history.

Scans the last N days of Gmail to find meetings the user agreed to that
don't have corresponding Google Calendar events, and adds them to the
stash calendar.

Designed to run as a Claude agent (via Claude Agent SDK) in the cloud
via e2b for the initial onboarding flow.
"""

from datetime import datetime, timedelta

from scheduler.auth.google_auth import get_credentials
from scheduler.calendar.client import CalendarClient
from scheduler.config import config
from scheduler.gmail.client import GmailClient


def run_onboarding():
    """Run the onboarding flow to backfill the stash calendar.

    Steps:
    1. Authenticate with Google
    2. Get or create the stash calendar
    3. Scan Gmail for the last ONBOARDING_LOOKBACK_DAYS days
    4. Use Claude to identify emails where the user agreed to meet
    5. Cross-reference with existing calendar events to avoid duplicates
    6. Add missing commitments to the stash calendar
    """
    # TODO: Implement
    # This will be the main onboarding entry point
    #
    # Key considerations:
    # - Search Gmail for scheduling-related emails (use queries like
    #   "let's meet", "schedule a call", "coffee", "lunch", etc.)
    # - For each potential commitment, check if a calendar event already exists
    # - Use Claude to extract: what, when, where, who
    # - Add confirmed commitments to the stash calendar with source="gmail_onboarding"
    raise NotImplementedError


if __name__ == "__main__":
    run_onboarding()
