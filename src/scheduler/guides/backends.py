"""Backend implementations for guide-writer agent tools.

Each backend provides the same interface — the agent doesn't know
whether it's calling Google APIs directly or going through HTTP.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Protocol

from scheduler.calendar.client import CalendarClient
from scheduler.config import config
from scheduler.gmail.client import GmailClient


class GuideBackend(Protocol):
    """Interface that both local and sandbox backends satisfy."""

    def search_emails(self, query: str, max_results: int = 50) -> dict: ...
    def read_thread(self, thread_id: str) -> dict: ...
    def get_calendar_events(self, start_date: str, end_date: str) -> dict: ...
    def write_guide(self, name: str, content: str) -> dict: ...


def _serialize_email(email) -> dict:
    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "sender": email.sender,
        "recipient": email.recipient,
        "cc": email.cc,
        "subject": email.subject,
        "body": email.body,
        "date": email.date.isoformat(),
        "snippet": email.snippet,
    }


def _serialize_event(event) -> dict:
    return {
        "id": event.id,
        "summary": event.summary,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "description": event.description,
        "source": event.source,
    }


class LocalGuideBackend:
    """Calls Gmail and Calendar APIs directly. Used for local/CLI and server mode."""

    def __init__(self, gmail: GmailClient, calendar: CalendarClient, user_id: str | None = None):
        self._gmail = gmail
        self._calendar = calendar
        self._user_id = user_id

    def search_emails(self, query: str, max_results: int = 50) -> dict:
        emails = self._gmail.search(query=query, max_results=max_results)
        return {"emails": [_serialize_email(e) for e in emails]}

    def read_thread(self, thread_id: str) -> dict:
        messages = self._gmail.get_thread(thread_id)
        return {"messages": [_serialize_email(e) for e in messages]}

    def get_calendar_events(self, start_date: str, end_date: str) -> dict:
        events = self._calendar.get_all_events(
            time_min=datetime.fromisoformat(start_date),
            time_max=datetime.fromisoformat(end_date),
        )
        return {"events": [_serialize_event(e) for e in events]}

    def write_guide(self, name: str, content: str) -> dict:
        from scheduler.guides import save_guide

        save_guide(name=name, content=content, user_id=self._user_id, source="onboarding")
        return {"status": "written", "name": name}


class UpdaterBackend:
    """Backend for the weekly guide updater agent.

    Loads edited draft diffs from the DB and provides surgical guide-write
    capability. Also accumulates agent log text per guide for the audit row.
    """

    def __init__(self, user_id: str, lookback_days: int = 7):
        self._user_id = user_id
        self._lookback_days = lookback_days
        self._agent_logs: dict[str, str] = {}

    def load_guide(self, name: str) -> str | None:
        from scheduler.guides import load_guide
        return load_guide(name, user_id=self._user_id)

    def get_edited_drafts(self) -> list[dict]:
        from scheduler.db import get_edited_drafts_since
        since = datetime.utcnow() - timedelta(days=self._lookback_days)
        return get_edited_drafts_since(self._user_id, since)

    def apply_guide_changes(
        self,
        guide_name: str,
        updated_content: str,
    ) -> None:
        """Write the updated guide content with source='updater'."""
        from scheduler.guides import save_guide
        save_guide(name=guide_name, content=updated_content, user_id=self._user_id, source="updater")

    def set_agent_log(self, guide_name: str, log: str) -> None:
        self._agent_logs[guide_name] = log

    def get_agent_log(self, guide_name: str) -> str:
        return self._agent_logs.get(guide_name, "")
