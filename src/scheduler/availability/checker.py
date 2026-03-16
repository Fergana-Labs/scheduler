"""Availability checker — finds open time slots for scheduling.

Checks the stash calendar (single source of truth) plus the user's primary
Google Calendar to find available meeting times.

Nice-to-have: Estimates "real" availability based on heuristics, e.g.:
- Dinner at 8pm means unavailable 7:30pm-10:30pm
- Events not accepted are still likely attended
- Known patterns (user never goes to research talks) can free up slots
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from scheduler.calendar.client import CalendarClient, Event


@dataclass
class TimeSlot:
    """A proposed meeting time."""

    start: datetime
    end: datetime


@dataclass
class AvailabilityResult:
    """Result of checking availability."""

    available_slots: list[TimeSlot]
    conflicts: list[Event]  # Events that block time in the requested range


class AvailabilityChecker:
    """Finds available time slots by checking all known commitments."""

    def __init__(self, calendar_client: CalendarClient):
        self._calendar = calendar_client

    def find_available_slots(
        self,
        range_start: datetime,
        range_end: datetime,
        duration_minutes: int = 30,
        working_hours: tuple[int, int] = (9, 18),
    ) -> AvailabilityResult:
        """Find available time slots within a date range.

        Args:
            range_start: Start of the range to search.
            range_end: End of the range to search.
            duration_minutes: How long the meeting needs to be.
            working_hours: Tuple of (start_hour, end_hour) for working hours.

        Returns:
            AvailabilityResult with available slots and blocking conflicts.
        """
        # TODO: Implement
        # 1. Get all events from stash + primary calendar in the range
        # 2. Build a list of busy periods (with buffer time around events)
        # 3. Find gaps that are at least duration_minutes long
        # 4. Filter to working hours
        # 5. Return available slots and the conflicts
        raise NotImplementedError

    def _apply_buffer(self, event: Event) -> tuple[datetime, datetime]:
        """Apply buffer time around an event for realistic availability.

        For example, a dinner at 8pm blocks 7:30pm-10:30pm.
        A 1-hour meeting needs ~10 min buffer on each side.

        Nice-to-have: Make this smarter based on event type.
        """
        # TODO: Implement
        # Default: 15 min buffer before, 15 min buffer after
        buffer = timedelta(minutes=15)
        return (event.start - buffer, event.end + buffer)

    def format_slots_for_email(self, slots: list[TimeSlot], max_suggestions: int = 3) -> str:
        """Format available slots as a human-readable string for an email draft.

        Args:
            slots: Available time slots.
            max_suggestions: Maximum number of times to suggest.

        Returns:
            Formatted string like "Tuesday 3/17 at 2:00 PM, Wednesday 3/18 at 10:00 AM"
        """
        # TODO: Implement
        raise NotImplementedError
