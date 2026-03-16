"""Google Calendar API client for the stash calendar."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """Represents a calendar event."""

    id: str | None
    summary: str
    start: datetime
    end: datetime
    description: str = ""
    source: str = ""  # Where this commitment was found (gmail, text, slack, etc.)


class CalendarClient:
    """Wrapper around the Google Calendar API.

    Manages the "stash calendar" — a real Google Calendar that serves as the
    single source of truth for all commitments, whether or not they have
    formal calendar invites.
    """

    def __init__(self, credentials, stash_calendar_name: str = "Stash Calendar"):
        self._credentials = credentials
        self._stash_calendar_name = stash_calendar_name
        self._service = None
        self._stash_calendar_id = None

    def _get_service(self):
        """Build and cache the Calendar API service."""
        # TODO: Build using googleapiclient.discovery.build("calendar", "v3", credentials=...)
        raise NotImplementedError

    def get_or_create_stash_calendar(self) -> str:
        """Get the stash calendar ID, creating it if it doesn't exist.

        Returns:
            The calendar ID of the stash calendar.
        """
        # TODO: Implement
        # 1. List all calendars
        # 2. Find one matching self._stash_calendar_name
        # 3. If not found, create it
        # 4. Cache and return the calendar ID
        raise NotImplementedError

    def get_all_events(
        self, time_min: datetime, time_max: datetime, include_primary: bool = True
    ) -> list[Event]:
        """Get all events across primary calendar and stash calendar.

        This is the main availability check — it combines the user's real
        calendar with the stash calendar to get a complete picture.

        Args:
            time_min: Start of the time range.
            time_max: End of the time range.
            include_primary: Whether to also check the user's primary calendar.

        Returns:
            All events in the time range, from both calendars.
        """
        # TODO: Implement
        # 1. Query stash calendar for events in range
        # 2. If include_primary, also query "primary" calendar
        # 3. Merge and return
        raise NotImplementedError

    def add_event(self, event: Event) -> str:
        """Add an event to the stash calendar.

        Args:
            event: The event to add.

        Returns:
            The ID of the created event.
        """
        # TODO: Implement using Calendar API events.insert
        raise NotImplementedError

    def update_event(self, event_id: str, event: Event) -> None:
        """Update an existing event on the stash calendar."""
        # TODO: Implement
        raise NotImplementedError

    def find_event(self, summary: str, time_min: datetime, time_max: datetime) -> Event | None:
        """Find an event by summary text within a time range.

        Useful for deduplication — checking if we already have this commitment.
        """
        # TODO: Implement
        raise NotImplementedError
