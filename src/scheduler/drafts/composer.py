"""Draft composer — generates email reply drafts with proposed meeting times.

Takes the scheduling context (who's asking, what they want, when you're free)
and uses Claude to compose a natural-sounding draft reply.
"""

import anthropic

from scheduler.availability.checker import AvailabilityChecker, TimeSlot
from scheduler.classifier.intent import ClassificationResult
from scheduler.config import config
from scheduler.gmail.client import Email, GmailClient


class DraftComposer:
    """Composes and creates draft replies for scheduling emails."""

    def __init__(
        self,
        gmail_client: GmailClient,
        availability_checker: AvailabilityChecker,
    ):
        self._gmail = gmail_client
        self._availability = availability_checker

    def compose_and_create_draft(self, email: Email, classification: ClassificationResult) -> str:
        """End-to-end: check availability, compose reply, create draft.

        Args:
            email: The incoming scheduling email.
            classification: The classification result with extracted details.

        Returns:
            The ID of the created Gmail draft.
        """
        # TODO: Implement
        # 1. Determine the date range to search for availability
        #    (e.g., next 2 weeks, or based on proposed times in the email)
        # 2. Find available slots using AvailabilityChecker
        # 3. Compose the reply text using Claude
        # 4. Create the draft via GmailClient
        raise NotImplementedError

    def _compose_reply(
        self,
        email: Email,
        classification: ClassificationResult,
        available_slots: list[TimeSlot],
    ) -> str:
        """Use Claude to compose a natural reply proposing meeting times.

        The reply should:
        - Match the tone of the incoming email
        - Propose 2-3 specific times
        - Be concise and professional
        """
        # TODO: Implement
        # 1. Build a prompt with the email context and available times
        # 2. Ask Claude to write a reply
        # 3. Return the composed text
        raise NotImplementedError
