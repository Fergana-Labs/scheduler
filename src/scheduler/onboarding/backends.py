"""Backend implementations for onboarding agent tools.

Each backend provides the same interface — the agent doesn't know
whether it's calling Google APIs directly or going through HTTP.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from scheduler.calendar.client import CalendarClient, Event
from scheduler.gmail.client import GmailClient


class BackfillBackend(Protocol):
    """Interface that both local and sandbox backends satisfy."""

    def search_emails(self, query: str, max_results: int = 50) -> dict: ...
    def read_thread(self, thread_id: str) -> dict: ...
    def find_event(self, summary: str, start_date: str, end_date: str) -> dict: ...
    def get_calendar_events(self, start_date: str, end_date: str) -> dict: ...
    def add_event(self, summary: str, start: str, end: str, description: str = "") -> dict: ...


def _serialize_email(email) -> dict:
    return {
        "id": email.id,
        "thread_id": email.thread_id,
        "sender": email.sender,
        "recipient": email.recipient,
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
    }


class LocalBackend:
    """Calls Gmail and Calendar APIs directly. Used for local/CLI mode."""

    def __init__(self, gmail: GmailClient, calendar: CalendarClient):
        self._gmail = gmail
        self._calendar = calendar

    def search_emails(self, query: str, max_results: int = 50) -> dict:
        emails = self._gmail.search(query=query, max_results=max_results)
        return {"emails": [_serialize_email(e) for e in emails]}

    def read_thread(self, thread_id: str) -> dict:
        messages = self._gmail.get_thread(thread_id)
        return {"messages": [_serialize_email(e) for e in messages]}

    def find_event(self, summary: str, start_date: str, end_date: str) -> dict:
        event = self._calendar.find_event(
            summary=summary,
            time_min=datetime.fromisoformat(start_date),
            time_max=datetime.fromisoformat(end_date),
        )
        if event:
            return {"exists": True, "event": _serialize_event(event)}
        return {"exists": False, "event": None}

    def get_calendar_events(self, start_date: str, end_date: str) -> dict:
        events = self._calendar.get_all_events(
            time_min=datetime.fromisoformat(start_date),
            time_max=datetime.fromisoformat(end_date),
        )
        return {"events": [_serialize_event(e) for e in events]}

    def add_event(self, summary: str, start: str, end: str, description: str = "") -> dict:
        event = Event(
            id=None,
            summary=summary,
            start=datetime.fromisoformat(start),
            end=datetime.fromisoformat(end),
            description=description,
            source="gmail",
        )
        event_id = self._calendar.add_event(event)
        return {"event_id": event_id, "status": "created"}
