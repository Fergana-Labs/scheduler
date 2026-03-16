"""Tests for the availability checker."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from scheduler.availability.checker import AvailabilityChecker, TimeSlot
from scheduler.calendar.client import CalendarClient, Event


def _make_checker(events: list[Event]) -> AvailabilityChecker:
    """Create a checker with a mock calendar client returning the given events."""
    mock_calendar = MagicMock(spec=CalendarClient)
    mock_calendar.get_all_events.return_value = events
    return AvailabilityChecker(mock_calendar)


# Monday March 16, 2026
MON = datetime(2026, 3, 16)


class TestFindAvailableSlots:
    def test_fully_open_day(self):
        checker = _make_checker([])
        result = checker.find_available_slots(
            MON.replace(hour=9), MON.replace(hour=18), duration_minutes=30
        )
        # One big slot from 9-18
        assert len(result.available_slots) == 1
        assert result.available_slots[0].start == MON.replace(hour=9)
        assert result.available_slots[0].end == MON.replace(hour=18)

    def test_single_event_creates_two_gaps(self):
        event = Event(
            id="1", summary="Standup", start=MON.replace(hour=12), end=MON.replace(hour=13)
        )
        checker = _make_checker([event])
        result = checker.find_available_slots(
            MON.replace(hour=9), MON.replace(hour=18), duration_minutes=30
        )
        # Should have two slots: 9:00-11:45 and 13:15-18:00 (15min buffers)
        assert len(result.available_slots) == 2
        assert result.available_slots[0].start == MON.replace(hour=9)
        assert result.available_slots[0].end == MON.replace(hour=11, minute=45)
        assert result.available_slots[1].start == MON.replace(hour=13, minute=15)
        assert result.available_slots[1].end == MON.replace(hour=18)

    def test_back_to_back_events_merge_busy_periods(self):
        events = [
            Event(id="1", summary="A", start=MON.replace(hour=10), end=MON.replace(hour=11)),
            Event(id="2", summary="B", start=MON.replace(hour=11), end=MON.replace(hour=12)),
        ]
        checker = _make_checker(events)
        result = checker.find_available_slots(
            MON.replace(hour=9), MON.replace(hour=18), duration_minutes=30
        )
        # Busy 9:45-12:15 (merged with buffers), so: 9:00-9:45 and 12:15-18:00
        assert len(result.available_slots) == 2

    def test_slot_too_short_is_excluded(self):
        # Event from 9:10-9:50 — with 15min buffers, blocks 8:55-10:05
        # So 9:00-8:55 is only 0 min (clamped), not enough for 30 min
        event = Event(
            id="1", summary="Quick sync", start=MON.replace(hour=9, minute=10),
            end=MON.replace(hour=9, minute=50),
        )
        checker = _make_checker([event])
        result = checker.find_available_slots(
            MON.replace(hour=9), MON.replace(hour=18), duration_minutes=30
        )
        # The gap 9:00-8:55 is negative after clamping, so only one slot after
        assert len(result.available_slots) == 1
        assert result.available_slots[0].start == MON.replace(hour=10, minute=5)

    def test_fully_booked_returns_no_slots(self):
        event = Event(
            id="1", summary="All day", start=MON.replace(hour=8), end=MON.replace(hour=19)
        )
        checker = _make_checker([event])
        result = checker.find_available_slots(
            MON.replace(hour=9), MON.replace(hour=18), duration_minutes=30
        )
        assert len(result.available_slots) == 0

    def test_skips_weekends(self):
        # Saturday March 21, 2026
        sat = datetime(2026, 3, 21)
        checker = _make_checker([])
        result = checker.find_available_slots(
            sat.replace(hour=9), sat.replace(hour=18), duration_minutes=30
        )
        assert len(result.available_slots) == 0

    def test_multi_day_range(self):
        checker = _make_checker([])
        # Mon-Wed
        result = checker.find_available_slots(
            MON.replace(hour=9),
            (MON + timedelta(days=2)).replace(hour=18),
            duration_minutes=30,
        )
        # 3 open days: Mon, Tue, Wed
        assert len(result.available_slots) == 3

    def test_conflicts_returned(self):
        event = Event(
            id="1", summary="Standup", start=MON.replace(hour=12), end=MON.replace(hour=13)
        )
        checker = _make_checker([event])
        result = checker.find_available_slots(
            MON.replace(hour=9), MON.replace(hour=18), duration_minutes=30
        )
        assert len(result.conflicts) == 1
        assert result.conflicts[0].summary == "Standup"


class TestFormatSlotsForEmail:
    def test_formats_slots(self):
        checker = _make_checker([])
        slots = [
            TimeSlot(start=datetime(2026, 3, 17, 14, 0), end=datetime(2026, 3, 17, 15, 0)),
            TimeSlot(start=datetime(2026, 3, 18, 10, 0), end=datetime(2026, 3, 18, 11, 0)),
        ]
        result = checker.format_slots_for_email(slots)
        assert "Tuesday" in result
        assert "2:00 PM" in result
        assert "Wednesday" in result
        assert "10:00 AM" in result

    def test_empty_slots(self):
        checker = _make_checker([])
        result = checker.format_slots_for_email([])
        assert "wasn't able to find" in result

    def test_spreads_across_days(self):
        checker = _make_checker([])
        slots = [
            TimeSlot(start=datetime(2026, 3, 17, 9, 0), end=datetime(2026, 3, 17, 10, 0)),
            TimeSlot(start=datetime(2026, 3, 17, 14, 0), end=datetime(2026, 3, 17, 15, 0)),
            TimeSlot(start=datetime(2026, 3, 18, 10, 0), end=datetime(2026, 3, 18, 11, 0)),
        ]
        result = checker.format_slots_for_email(slots, max_suggestions=2)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 2
        # Should pick one from each day
        assert "Tuesday" in lines[0]
        assert "Wednesday" in lines[1]
