"""Eval backends — record once, replay forever.

Fixture format:
{
  "metadata": {"recorded_at": "...", ...},
  "messages": [ {id, thread_id, sender, recipient, cc, subject, body, date, snippet}, ... ],
  "events": [ {id, summary, start, end, description, source}, ... ],
  "timezone": "America/Los_Angeles",
  "guides": {"scheduling_preferences": "...", "email_style": "..."}
}

The fixture is a flat dump of the user's inbox + calendar. Replay backends
search/filter this data in-memory so the agent gets realistic results for
any query it makes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixture I/O
# ---------------------------------------------------------------------------

def save_fixture(
    path: str,
    messages: list[dict],
    events: list[dict],
    timezone: str,
    guides: dict[str, str | None],
    metadata: dict | None = None,
) -> None:
    data = {
        "metadata": {
            "recorded_at": datetime.now().isoformat(),
            **(metadata or {}),
        },
        "messages": messages,
        "events": events,
        "timezone": timezone,
        "guides": guides,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_fixture(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# In-memory Gmail search over fixture messages
# ---------------------------------------------------------------------------

def _search_messages(messages: list[dict], query: str, max_results: int = 50) -> list[dict]:
    """Naive Gmail-like search over fixture messages.

    Supports:
      - from:me / from:<addr>  — filter by sender
      - bare keywords           — match against subject + body + snippet
    """
    terms = query.strip().split()
    from_filter = None
    keywords = []

    for term in terms:
        if term.lower().startswith("from:"):
            from_filter = term[5:].lower()
        else:
            keywords.append(term.lower())

    results = []
    for msg in messages:
        # from: filter
        if from_filter:
            sender = (msg.get("sender") or "").lower()
            if from_filter == "me":
                # "from:me" — heuristic: sender contains the user's domain
                # or sender field is empty (shouldn't happen). We can't know
                # the user's exact email, so match on the most common sender.
                # Better heuristic: skip this message if sender looks like
                # someone else. We'll rely on keyword matching too.
                pass  # don't filter on from:me, just use keywords
            elif from_filter not in sender:
                continue

        # keyword matching — all keywords must appear in subject, body, or snippet
        if keywords:
            searchable = " ".join([
                (msg.get("subject") or ""),
                (msg.get("body") or ""),
                (msg.get("snippet") or ""),
            ]).lower()
            if not all(kw in searchable for kw in keywords):
                continue

        results.append(msg)
        if len(results) >= max_results:
            break

    return results


def _filter_events(events: list[dict], start_date: str, end_date: str) -> list[dict]:
    """Filter fixture events by date range."""
    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)

    results = []
    for event in events:
        event_start = datetime.fromisoformat(event["start"])
        event_end = datetime.fromisoformat(event["end"])
        # Include if event overlaps with the requested window
        if event_end > start and event_start < end:
            results.append(event)
    return results


# ---------------------------------------------------------------------------
# Serialization helpers (used by cmd_record)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Guide backends (GuideBackend protocol)
#
# search_emails returns {"emails": [...]}
# read_thread returns {"messages": [...]}
# get_calendar_events returns {"events": [...]}
# ---------------------------------------------------------------------------

class ReplayGuideBackend:
    """Replays from a fixture. Searches/filters in-memory. No API access."""

    def __init__(self, fixture: dict):
        self._messages = fixture.get("messages", [])
        self._events = fixture.get("events", [])
        # Group messages by thread_id for fast thread lookups
        self._threads: dict[str, list[dict]] = {}
        for msg in self._messages:
            tid = msg.get("thread_id", "")
            self._threads.setdefault(tid, []).append(msg)
        self.captured_guides: dict[str, str] = {}

    def search_emails(self, query: str, max_results: int = 50) -> dict:
        results = _search_messages(self._messages, query, max_results)
        return {"emails": results}

    def read_thread(self, thread_id: str) -> dict:
        messages = self._threads.get(thread_id, [])
        return {"messages": messages}

    def get_calendar_events(self, start_date: str, end_date: str) -> dict:
        results = _filter_events(self._events, start_date, end_date)
        return {"events": results}

    def write_guide(self, name: str, content: str) -> dict:
        self.captured_guides[name] = content
        return {"status": "captured", "name": name}


# ---------------------------------------------------------------------------
# Draft backends (DraftBackend protocol)
#
# read_thread returns list[dict] (bare list)
# get_calendar_events returns list[dict] (bare list)
# ---------------------------------------------------------------------------

class ReplayDraftBackend:
    """Replays from a fixture. Searches/filters in-memory. No API access."""

    def __init__(self, fixture: dict):
        self._messages = fixture.get("messages", [])
        self._events = fixture.get("events", [])
        self._timezone = fixture.get("timezone", "UTC")
        self._guides = fixture.get("guides", {})
        # Group messages by thread_id
        self._threads: dict[str, list[dict]] = {}
        for msg in self._messages:
            tid = msg.get("thread_id", "")
            self._threads.setdefault(tid, []).append(msg)

        self.captured_draft: dict | None = None
        self.captured_sent: dict | None = None
        self.captured_events: list[dict] = []

    def load_guide(self, name: str) -> str | None:
        return self._guides.get(name)

    def get_user_timezone(self) -> str:
        return self._timezone

    def get_calendar_events(self, start_date: str, end_date: str) -> list[dict]:
        return _filter_events(self._events, start_date, end_date)

    def read_thread(self, thread_id: str) -> list[dict]:
        return self._threads.get(thread_id, [])

    def create_draft(self, args: dict) -> dict:
        self.captured_draft = args
        return {"draft_id": "dry-run-draft"}

    def send_email(self, args: dict) -> dict:
        self.captured_sent = args
        return {"message_id": "dry-run-sent", "status": "captured"}

    def add_calendar_event(self, args: dict) -> dict:
        self.captured_events.append(args)
        return {"event_id": "dry-run-event"}


class ReplayBackfillBackend:
    """Replays from a fixture for the calendar backfill agent."""

    def __init__(self, fixture: dict):
        self._messages = fixture.get("messages", [])
        self._events = fixture.get("events", [])
        self._threads: dict[str, list[dict]] = {}
        for msg in self._messages:
            tid = msg.get("thread_id", "")
            self._threads.setdefault(tid, []).append(msg)

        self.captured_events: list[dict] = []

    def search_emails(self, query: str, max_results: int = 50) -> dict:
        results = _search_messages(self._messages, query, max_results)
        return {"emails": results}

    def read_thread(self, thread_id: str) -> dict:
        messages = self._threads.get(thread_id, [])
        return {"messages": messages}

    def find_event(self, summary: str, start_date: str, end_date: str) -> dict:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        for event in self._events + self.captured_events:
            event_start = datetime.fromisoformat(event["start"])
            if start <= event_start <= end and summary.lower() in event["summary"].lower():
                return {"exists": True, "event": event}
        return {"exists": False, "event": None}

    def get_calendar_events(self, start_date: str, end_date: str) -> dict:
        all_events = self._events + self.captured_events
        results = _filter_events(all_events, start_date, end_date)
        return {"events": results}

    def add_event(self, summary: str, start: str, end: str, description: str = "") -> dict:
        event = {
            "id": f"eval-event-{len(self.captured_events)}",
            "summary": summary,
            "start": start,
            "end": end,
            "description": description,
            "source": "onboarding-eval",
        }
        self.captured_events.append(event)
        return {"event_id": event["id"], "status": "captured"}
