"""Gmail API client for reading emails and creating drafts."""

from dataclasses import dataclass
from datetime import datetime


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
        # TODO: Build using googleapiclient.discovery.build("gmail", "v1", credentials=...)
        raise NotImplementedError

    def get_recent_emails(self, max_results: int = 50, since: datetime | None = None) -> list[Email]:
        """Fetch recent emails from the inbox.

        Args:
            max_results: Maximum number of emails to return.
            since: Only return emails after this datetime.

        Returns:
            List of Email objects, newest first.
        """
        # TODO: Implement using Gmail API messages.list + messages.get
        raise NotImplementedError

    def get_email(self, message_id: str) -> Email:
        """Fetch a single email by ID."""
        # TODO: Implement
        raise NotImplementedError

    def get_thread(self, thread_id: str) -> list[Email]:
        """Fetch all messages in a thread."""
        # TODO: Implement using Gmail API threads.get
        raise NotImplementedError

    def create_draft(self, thread_id: str, to: str, subject: str, body: str) -> str:
        """Create a draft reply in a thread.

        Args:
            thread_id: The thread to reply to.
            to: Recipient email address.
            subject: Email subject (usually "Re: ...").
            body: The draft body with proposed times.

        Returns:
            The ID of the created draft.
        """
        # TODO: Implement using Gmail API drafts.create
        # The draft should appear as a reply in the thread
        raise NotImplementedError

    def search(self, query: str, max_results: int = 100) -> list[Email]:
        """Search emails using Gmail search syntax.

        Useful for onboarding — finding emails where user agreed to meetings.

        Args:
            query: Gmail search query (e.g., "let's meet" or "schedule a call").
            max_results: Maximum results to return.
        """
        # TODO: Implement using Gmail API messages.list with q parameter
        raise NotImplementedError
