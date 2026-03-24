"""Evals for the invite verification classifier.

Each test case sends a real LLM call to verify the classifier behaves correctly.
Run with: pytest tests/test_invite_verification.py -v -s
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from scheduler.classifier.intent import verify_sent_message_for_invite
from scheduler.db import PendingInviteRow


def _make_pending(
    attendees=None,
    summary="Coffee chat",
    start="2026-03-26T14:00:00-07:00",
    end="2026-03-26T15:00:00-07:00",
    google_meet=False,
    location="",
) -> PendingInviteRow:
    return PendingInviteRow(
        id="test-invite-id",
        user_id="test-user-id",
        thread_id="test-thread-id",
        attendee_emails=attendees or ["alice@example.com"],
        event_summary=summary,
        event_start=datetime.fromisoformat(start),
        event_end=datetime.fromisoformat(end),
        add_google_meet=google_meet,
        created_at=datetime.now(timezone.utc),
        location=location,
    )


# --- Test cases ---


@dataclass
class VerificationEval:
    name: str
    sent_body: str
    expected_action: str  # "send" | "update" | "skip"
    pending: PendingInviteRow | None = None
    thread_messages: list[dict] | None = None


EVAL_CASES = [
    # --- SEND cases: message confirms the meeting as proposed ---
    VerificationEval(
        name="simple_confirmation",
        sent_body="Sounds great! Thursday at 2pm works for me. Looking forward to it!",
        expected_action="send",
    ),
    VerificationEval(
        name="confirmation_with_location",
        sent_body="Perfect, let's do Thursday at 2pm. I'll be at the Blue Bottle on Valencia St.",
        expected_action="send",
        pending=_make_pending(location="Blue Bottle on Valencia St."),
    ),
    VerificationEval(
        name="confirmation_mentions_invite",
        sent_body="Thursday 2pm works! I'll send over a calendar invite.",
        expected_action="send",
    ),
    VerificationEval(
        name="brief_confirmation",
        sent_body="Works for me, see you then!",
        expected_action="send",
        thread_messages=[
            {
                "sender": "alice@example.com",
                "body": "How about Thursday at 2pm for coffee?",
                "date": "2026-03-25T10:00:00-07:00",
            },
        ],
    ),
    VerificationEval(
        name="confirmation_group_meeting",
        sent_body="Thursday at 2pm works for all of us. See you there!",
        expected_action="send",
        pending=_make_pending(attendees=["alice@example.com", "bob@example.com"]),
    ),

    # --- SKIP cases: message declines, cancels, or changes topic ---
    VerificationEval(
        name="polite_decline",
        sent_body="Thanks for reaching out, but I'm going to pass on this. Best of luck!",
        expected_action="skip",
    ),
    VerificationEval(
        name="explicit_cancel",
        sent_body="Hey, I need to cancel our meeting on Thursday. Something came up. Sorry about that!",
        expected_action="skip",
    ),
    VerificationEval(
        name="topic_change_no_meeting",
        sent_body="Thanks for the info! I'll review the document and get back to you by end of week.",
        expected_action="skip",
    ),
    VerificationEval(
        name="not_interested",
        sent_body="Actually I am going to have to pass on this, sorry!",
        expected_action="skip",
    ),
    VerificationEval(
        name="postpone_indefinitely",
        sent_body="Let's put this on hold for now. I'll reach out when things settle down.",
        expected_action="skip",
    ),
    VerificationEval(
        name="delegate_to_someone_else",
        sent_body="I think you should connect with my colleague Sarah on this. I've CC'd her.",
        expected_action="skip",
    ),
    VerificationEval(
        name="asks_for_different_times",
        sent_body="Thursday doesn't work for me. Could you send over some other options?",
        expected_action="skip",
    ),

    # --- UPDATE cases: meeting confirmed but details changed ---
    VerificationEval(
        name="time_change",
        sent_body="Thursday works but can we do 3pm instead of 2pm? Same place.",
        expected_action="update",
    ),
    VerificationEval(
        name="date_change",
        sent_body="I can't do Thursday, but Friday at 2pm works great. Let's do that instead!",
        expected_action="update",
    ),
    VerificationEval(
        name="add_google_meet",
        sent_body="Thursday at 2pm works! Can we do it over Google Meet instead of in person?",
        expected_action="update",
        pending=_make_pending(google_meet=False),
    ),
    VerificationEval(
        name="longer_meeting",
        sent_body="Thursday at 2pm is great. Could we make it 90 minutes? I have a lot to discuss.",
        expected_action="update",
    ),
    VerificationEval(
        name="location_change",
        sent_body="Thursday at 2pm works! But let's meet at Philz Coffee on 24th instead.",
        expected_action="update",
        pending=_make_pending(location="Blue Bottle on Valencia St."),
    ),
    VerificationEval(
        name="add_attendee",
        sent_body="Thursday at 2pm is great. I'm also going to bring Bob — I've CC'd him.",
        expected_action="update",
        pending=_make_pending(attendees=["alice@example.com"]),
    ),
    VerificationEval(
        name="add_location_to_no_location",
        sent_body="Thursday at 2pm works. Let's meet at the WeWork on Market St.",
        expected_action="update",
        pending=_make_pending(location=""),
    ),
]


@pytest.mark.parametrize(
    "case",
    EVAL_CASES,
    ids=[c.name for c in EVAL_CASES],
)
def test_invite_verification(case: VerificationEval):
    pending = case.pending or _make_pending()
    thread = case.thread_messages or []

    result = verify_sent_message_for_invite(
        sent_message_body=case.sent_body,
        sent_message_sender="henry@ferganalabs.com",
        thread_messages=thread,
        pending_invite=pending,
    )

    print(f"\n  [{case.name}] action={result.action} reason={result.reason}")
    if result.action == "update":
        updates = {
            k: v for k, v in {
                "attendees": result.updated_attendee_emails,
                "summary": result.updated_event_summary,
                "start": result.updated_event_start,
                "end": result.updated_event_end,
                "meet": result.updated_add_google_meet,
                "location": result.updated_location,
            }.items() if v is not None
        }
        print(f"  updates: {updates}")

    assert result.action == case.expected_action, (
        f"Expected action '{case.expected_action}' but got '{result.action}'. "
        f"Reason: {result.reason}"
    )
