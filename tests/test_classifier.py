"""Tests for the scheduling intent classifier."""

import pytest

from scheduler.classifier.intent import (
    ClassificationResult,
    SchedulingIntent,
    classify_email,
)


@pytest.mark.skip(reason="Not yet implemented")
class TestClassifyEmail:
    def test_scheduling_request(self):
        result = classify_email(
            subject="Coffee next week?",
            body="Hey! Would love to catch up over coffee next week. When works for you?",
            sender="alice@example.com",
        )
        assert result.intent == SchedulingIntent.REQUESTING_MEETING

    def test_not_scheduling(self):
        result = classify_email(
            subject="Q4 Report",
            body="Please find attached the Q4 report. Let me know if you have questions.",
            sender="bob@example.com",
        )
        assert result.intent == SchedulingIntent.NOT_SCHEDULING

    def test_proposing_specific_times(self):
        result = classify_email(
            subject="Re: Meeting",
            body="How about Tuesday at 2pm or Wednesday at 10am?",
            sender="carol@example.com",
        )
        assert result.intent == SchedulingIntent.PROPOSING_TIMES
        assert len(result.proposed_times) >= 1
