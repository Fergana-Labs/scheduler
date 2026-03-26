"""Booking automation — fetch available times and book slots on Calendly / Cal.com.

Two-call API:
  1. get_available_times(url, date) -> list of time slots
  2. book_slot(url, date, time, name, email) -> confirmation

Uses deterministic Playwright scripts.
"""

from __future__ import annotations

import logging
from datetime import date

from scheduler.booking.models import AvailableTimesResult, BookingResult, BookingStatus

logger = logging.getLogger(__name__)


async def get_available_times(
    url: str, target_date: date, headless: bool = True
) -> AvailableTimesResult:
    """Get available time slots from a booking page."""
    from scheduler.booking.playwright_flow import get_times_playwright

    try:
        times = await get_times_playwright(url, target_date, headless)
        return AvailableTimesResult(times=times, date=target_date)
    except Exception as e:
        return AvailableTimesResult(
            times=[], date=target_date, error_detail=str(e)
        )


async def book_slot(
    url: str,
    target_date: date,
    time: str,
    name: str,
    email: str,
    headless: bool = True,
    title: str = "",
) -> BookingResult:
    """Book a specific time slot on a booking page."""
    from scheduler.booking.playwright_flow import book_slot_playwright

    try:
        return await book_slot_playwright(
            url, target_date, time, name, email, headless, title=title
        )
    except Exception as e:
        return BookingResult(status=BookingStatus.ERROR, error_detail=str(e))
