"""Onboarding agent — backfills the stash calendar from Gmail history.

Entry point for the local (CLI) onboarding mode. For sandbox mode,
see scheduler.sandbox.onboarding.
"""

import anyio

from scheduler.onboarding.agent import _run_backfill_async as _run_backfill
from scheduler.onboarding.backends import LocalBackend

from scheduler.auth.google_auth import get_credentials
from scheduler.calendar.client import CalendarClient
from scheduler.config import config
from scheduler.gmail.client import GmailClient


async def _run_onboarding_all():
    """Run backfill + both guide writers in parallel."""
    from scheduler.guides.backends import LocalGuideBackend
    from scheduler.guides.preferences import run_preferences_agent
    from scheduler.guides.style import run_style_agent

    creds = get_credentials()
    gmail = GmailClient(creds)
    calendar = CalendarClient(creds, config.stash_calendar_name)
    calendar.get_or_create_stash_calendar()

    onboarding_backend = LocalBackend(gmail, calendar)
    guide_backend = LocalGuideBackend(gmail, calendar)

    async with anyio.create_task_group() as tg:
        tg.start_soon(_run_backfill, onboarding_backend, config.onboarding_lookback_days)
        tg.start_soon(run_preferences_agent, guide_backend)
        tg.start_soon(run_style_agent, guide_backend)


def run_onboarding():
    """Run onboarding: backfill stash calendar + generate guide files.

    Launches three agents in parallel:
    1. Backfill agent — searches Gmail and adds commitments to the stash calendar
    2. Preferences agent — analyzes scheduling patterns and writes a guide
    3. Style agent — analyzes email writing style and writes a guide
    """
    anyio.run(_run_onboarding_all)


if __name__ == "__main__":
    run_onboarding()
