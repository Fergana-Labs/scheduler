"""Tests for the availability checker."""

import pytest
from datetime import datetime, timedelta

from scheduler.availability.checker import AvailabilityChecker, TimeSlot
from scheduler.calendar.client import Event


@pytest.mark.skip(reason="Not yet implemented")
class TestAvailabilityChecker:
    def test_finds_open_slots(self):
        pass

    def test_respects_working_hours(self):
        pass

    def test_applies_buffer_around_events(self):
        pass

    def test_no_slots_when_fully_booked(self):
        pass
