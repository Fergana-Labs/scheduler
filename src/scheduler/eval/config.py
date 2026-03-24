"""Canonical eval sets — thread IDs, expected classifications, and reference drafts."""

from dataclasses import dataclass


@dataclass
class EvalCase:
    thread_id: str
    description: str  # human-readable label for this case

    # Expected classifier output
    expected_intent: str  # e.g. "requesting_meeting", "proposing_times", "not_scheduling"
    expected_is_sales: bool = False

    # Whose inbox this thread came from (used so the agent knows who it's composing for)
    user_email: str = "henry@ferganalabs.com"

    # Reference draft — what a good response looks like.
    # None means "no draft should be created" (e.g. not_scheduling, already resolved).
    expected_draft: str | None = None


# Add eval cases here after running `python -m scheduler.eval list --fixture ...`
EVAL_CASES: list[EvalCase] = [
    # EvalCase(
    #     thread_id="18f3a2b...",
    #     description="Alice asks for coffee next week",
    #     expected_intent="requesting_meeting",
    #     expected_draft="Hey Alice- How's Thursday at 10am PT or Friday at 2pm PT? ...",
    # ),
]
