"""Gmail API client for reading emails and creating drafts."""

import base64
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build


@dataclass
class Email:
    """Represents a Gmail message."""

    id: str
    thread_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    date: datetime
    snippet: str


class GmailClient:
    """Wrapper around the Gmail API.

    Handles reading emails, searching for messages, and creating drafts.
    Uses the same OAuth privileges that Fyxer uses to create drafts.
    """

    def __init__(self, credentials):
        """Initialize with Google OAuth2 credentials."""
        self._credentials = credentials
        self._service = None  # Lazily initialized

    def _get_service(self):
        """Build and cache the Gmail API service."""
        if self._service is None:
            self._service = build("gmail", "v1", credentials=self._credentials)
        return self._service

    def _extract_body(self, payload: dict) -> str:
        """Recursively walk the Gmail message payload to find body text.

        Prefers text/plain; falls back to text/html (LLM consumers handle HTML).
        """
        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")

        # Single-part message with text/plain
        if mime_type == "text/plain" and body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        # Multipart — recurse into parts
        parts = payload.get("parts", [])
        # First pass: look for text/plain
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # Recurse into nested multipart
            result = self._extract_body(part)
            if result:
                return result

        # Second pass: fall back to text/html
        if mime_type == "text/html" and body_data:
            return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        return ""

    def _parse_message(self, msg_data: dict) -> Email:
        """Convert a Gmail API full-format message dict into an Email."""
        payload = msg_data.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        date_str = headers.get("date", "")
        try:
            date = parsedate_to_datetime(date_str)
        except Exception:
            date = datetime.now()

        return Email(
            id=msg_data["id"],
            thread_id=msg_data["threadId"],
            sender=headers.get("from", ""),
            recipient=headers.get("to", ""),
            subject=headers.get("subject", ""),
            body=self._extract_body(payload),
            date=date,
            snippet=msg_data.get("snippet", ""),
        )

    def _list_message_stubs(self, query: str | None, max_results: int) -> list[dict]:
        """Paginate through messages.list and return id/threadId stubs."""
        service = self._get_service()
        stubs = []
        page_token = None

        while len(stubs) < max_results:
            kwargs = {
                "userId": "me",
                "maxResults": min(max_results - len(stubs), 500),
            }
            if query:
                kwargs["q"] = query
            if page_token:
                kwargs["pageToken"] = page_token

            result = service.users().messages().list(**kwargs).execute()

            for msg in result.get("messages", []):
                stubs.append(msg)
                if len(stubs) >= max_results:
                    break

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return stubs

    def _fetch_messages(self, stubs: list[dict]) -> list[Email]:
        """Hydrate message stubs into full Email objects."""
        service = self._get_service()
        emails = []
        for stub in stubs:
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=stub["id"], format="full")
                .execute()
            )
            emails.append(self._parse_message(msg_data))
        return emails

    def get_recent_emails(self, max_results: int = 50, since: datetime | None = None) -> list[Email]:
        """Fetch recent emails from the inbox.

        Args:
            max_results: Maximum number of emails to return.
            since: Only return emails after this datetime.

        Returns:
            List of Email objects, newest first.
        """
        query = None
        if since:
            epoch = int(since.timestamp())
            query = f"after:{epoch}"

        stubs = self._list_message_stubs(query, max_results)
        return self._fetch_messages(stubs)

    def get_email(self, message_id: str) -> Email:
        """Fetch a single email by ID."""
        service = self._get_service()
        msg_data = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        return self._parse_message(msg_data)

    def get_thread(self, thread_id: str) -> list[Email]:
        """Fetch all messages in a thread."""
        service = self._get_service()
        thread_data = (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )
        return [self._parse_message(m) for m in thread_data.get("messages", [])]

    def create_draft(self, thread_id: str, to: str, subject: str, body: str, content_type: str = "plain") -> str:
        """Create a draft reply in a thread.

        Args:
            thread_id: The thread to reply to.
            to: Recipient email address.
            subject: Email subject (usually "Re: ...").
            body: The draft body with proposed times.

        Returns:
            The ID of the created draft.
        """
        service = self._get_service()

        # Fetch thread to get Message-Id of last message for threading headers
        thread_data = (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata", metadataHeaders=["Message-Id"])
            .execute()
        )
        messages = thread_data.get("messages", [])
        message_id_header = ""
        if messages:
            last_msg = messages[-1]
            for header in last_msg.get("payload", {}).get("headers", []):
                if header["name"].lower() == "message-id":
                    message_id_header = header["value"]
                    break

        # Build MIME message
        mime_msg = MIMEText(body, content_type)
        mime_msg["To"] = to
        mime_msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if message_id_header:
            mime_msg["In-Reply-To"] = message_id_header
            mime_msg["References"] = message_id_header

        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("ascii")

        draft = (
            service.users()
            .drafts()
            .create(
                userId="me",
                body={"message": {"raw": raw, "threadId": thread_id}},
            )
            .execute()
        )
        return draft["id"]

    def watch(self, topic_name: str) -> dict:
        """Start receiving push notifications for new emails.

        Calls Gmail users.watch() to register for push notifications via
        Google Cloud Pub/Sub. Must be renewed before expiration (~ 7 days).

        Args:
            topic_name: Full Pub/Sub topic name, e.g.
                        "projects/my-project/topics/gmail-notifications".

        Returns:
            Dict with 'historyId' (str) and 'expiration' (epoch ms str).
        """
        service = self._get_service()
        result = (
            service.users()
            .watch(
                userId="me",
                body={
                    "topicName": topic_name,
                    "labelIds": ["INBOX"],
                },
            )
            .execute()
        )
        return {"historyId": result["historyId"], "expiration": result["expiration"]}

    def get_history(self, start_history_id: str) -> list[str]:
        """Get message IDs added to the inbox since a given history ID.

        Args:
            start_history_id: The history ID to start from (from watch() or
                              a previous push notification).

        Returns:
            List of new message IDs.
        """
        service = self._get_service()
        message_ids = []
        page_token = None

        while True:
            kwargs = {
                "userId": "me",
                "startHistoryId": start_history_id,
                "historyTypes": ["messageAdded"],
                "labelId": "INBOX",
            }
            if page_token:
                kwargs["pageToken"] = page_token

            result = service.users().history().list(**kwargs).execute()

            for record in result.get("history", []):
                for msg_added in record.get("messagesAdded", []):
                    message_ids.append(msg_added["message"]["id"])

            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return message_ids

    def search(self, query: str, max_results: int = 100) -> list[Email]:
        """Search emails using Gmail search syntax.

        Useful for onboarding — finding emails where user agreed to meetings.

        Args:
            query: Gmail search query (e.g., "let's meet" or "schedule a call").
            max_results: Maximum results to return.
        """
        stubs = self._list_message_stubs(query, max_results)
        return self._fetch_messages(stubs)
