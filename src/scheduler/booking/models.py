"""Data models for booking automation."""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class BookingPlatform(Enum):
    CALENDLY = "calendly"
    CAL_COM = "cal_com"


class BookingStatus(Enum):
    SUCCESS = "success"
    NO_AVAILABILITY = "no_availability"
    SLOT_TAKEN = "slot_taken"
    ERROR = "error"


@dataclass
class BookingResult:
    status: BookingStatus
    confirmation_message: str | None = None
    error_detail: str | None = None


@dataclass
class AvailableTimesResult:
    times: list[str]
    date: date
    error_detail: str | None = None


def detect_platform(url: str) -> BookingPlatform:
    """Detect booking platform from URL."""
    if "calendly.com" in url:
        return BookingPlatform.CALENDLY
    elif "cal.com" in url:
        return BookingPlatform.CAL_COM
    raise ValueError(f"Unsupported booking platform: {url}")
