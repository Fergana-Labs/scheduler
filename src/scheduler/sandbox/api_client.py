"""HTTP client for calling the control plane from inside the sandbox."""

import httpx


class ControlPlaneClient:
    """Thin wrapper around the control plane API.

    Each method corresponds to a control plane endpoint. Used by the
    sandbox agent tools to call Gmail/Calendar operations without
    holding any Google credentials.
    """

    def __init__(self, base_url: str, session_token: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {session_token}"}

    def _url(self, path: str) -> str:
        return f"{self._base_url}/api/v1{path}"

    def _post(self, path: str, body: dict) -> dict:
        resp = httpx.post(self._url(path), json=body, headers=self._headers, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str) -> dict:
        resp = httpx.get(self._url(path), headers=self._headers, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def search_emails(self, query: str, max_results: int = 50) -> dict:
        return self._post("/gmail/search", {"query": query, "max_results": max_results})

    def read_thread(self, thread_id: str) -> dict:
        return self._get(f"/gmail/thread/{thread_id}")

    def get_email(self, message_id: str) -> dict:
        return self._get(f"/gmail/message/{message_id}")

    def get_user_timezone(self) -> str:
        return self._get("/calendar/timezone").get("timezone", "UTC")

    def get_calendar_events(self, start_date: str, end_date: str) -> dict:
        return self._post("/calendar/events", {"start_date": start_date, "end_date": end_date})

    def find_event(self, summary: str, start_date: str, end_date: str) -> dict:
        return self._post(
            "/calendar/find",
            {"summary": summary, "start_date": start_date, "end_date": end_date},
        )

    def add_event(self, summary: str, start: str, end: str, description: str = "") -> dict:
        return self._post(
            "/calendar/add",
            {"summary": summary, "start": start, "end": end, "description": description},
        )

    def create_draft(self, **kwargs) -> dict:
        return self._post("/gmail/draft", kwargs)

    def send_email(self, **kwargs) -> dict:
        return self._post("/gmail/send", kwargs)

    def write_guide(self, name: str, content: str) -> dict:
        return self._post("/guides/write", {"name": name, "content": content})

    def read_guide(self, name: str) -> dict:
        return self._post("/guides/read", {"name": name})
