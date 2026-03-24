"""Eval backend — mocks Gmail/Calendar so the draft composer runs against fixtures."""

import json
from datetime import datetime
from pathlib import Path


FIXTURES_PATH = Path(__file__).parent / "draft_canonical_evals.json"


class EvalDraftBackend:
    """Drop-in replacement for LocalDraftBackend that serves fixture data."""

    def __init__(
        self,
        fixtures_path: Path = FIXTURES_PATH,
        calendar_events: list[dict] | None = None,
        timezone: str = "America/Los_Angeles",
        guides: dict[str, str] | None = None,
    ):
        with open(fixtures_path) as f:
            raw = json.load(f)

        self._threads: dict[str, list[dict]] = {
            case["thread_id"]: case["messages"] for case in raw
        }

        self._calendar_events = calendar_events or []
        self._timezone = timezone
        self._guides = guides or {}
        self.drafts_created: list[dict] = []
        self.emails_sent: list[dict] = []
        self.events_added: list[dict] = []

    def load_guide(self, name: str) -> str | None:
        return self._guides.get(name)

    def get_user_timezone(self) -> str:
        return self._timezone

    def get_calendar_events(self, start_date: str, end_date: str) -> list[dict]:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        return [
            e for e in self._calendar_events
            if start <= datetime.fromisoformat(e["start"]) <= end
        ]

    def read_thread(self, thread_id: str) -> list[dict]:
        if thread_id not in self._threads:
            raise ValueError(f"Thread {thread_id} not found in fixtures")
        return self._threads[thread_id]

    def create_draft(self, args: dict) -> dict:
        draft_id = f"eval-draft-{len(self.drafts_created)}"
        self.drafts_created.append({**args, "draft_id": draft_id})
        return {"draft_id": draft_id}

    def send_email(self, args: dict) -> dict:
        msg_id = f"eval-sent-{len(self.emails_sent)}"
        self.emails_sent.append({**args, "message_id": msg_id})
        return {"message_id": msg_id, "status": "sent"}

    def add_calendar_event(self, args: dict) -> dict:
        event_id = f"eval-event-{len(self.events_added)}"
        self.events_added.append({**args, "event_id": event_id})
        return {"event_id": event_id}
