"""Sandbox entry point for the draft composer agent."""

from __future__ import annotations

import json
import os
from pathlib import Path

from scheduler.drafts.composer import DraftBackend, DraftComposer
from scheduler.sandbox.api_client import ControlPlaneClient


class ControlPlaneDraftBackend(DraftBackend):
    def __init__(self, client: ControlPlaneClient):
        self._client = client

    def load_guide(self, name: str) -> str | None:
        try:
            return self._client.read_guide(name).get("content")
        except Exception:
            return None

    def get_user_timezone(self) -> str:
        return self._client.get_user_timezone()

    def get_calendar_events(self, start_date: str, end_date: str) -> list[dict]:
        return self._client.get_calendar_events(start_date, end_date).get("events", [])

    def read_thread(self, thread_id: str) -> list[dict]:
        return self._client.read_thread(thread_id).get("messages", [])

    def create_draft(self, args: dict) -> dict:
        return self._client.create_draft(**args)

    def send_email(self, args: dict) -> dict:
        return self._client.send_email(**args)

    def add_calendar_event(self, args: dict) -> dict:
        return self._client.add_event(
            summary=args["summary"],
            start=args["start"],
            end=args["end"],
            description=args.get("description", ""),
        )


def run_drafting() -> None:
    control_plane_url = os.environ["CONTROL_PLANE_URL"]
    session_token = os.environ["SESSION_TOKEN"]
    autopilot = os.environ.get("AUTOPILOT_ENABLED", "0") == "1"

    workdir = Path("/home/user/scheduler")
    email = json.loads((workdir / "draft_email.json").read_text())
    classification = json.loads((workdir / "draft_classification.json").read_text())

    backend = ControlPlaneDraftBackend(ControlPlaneClient(control_plane_url, session_token))
    composer = DraftComposer(backend, user_id="sandbox", autopilot=autopilot)
    result = composer.compose_and_create_draft(email, classification)
    print(f"DRAFT_RESULT:{result or ''}")


if __name__ == "__main__":
    run_drafting()
