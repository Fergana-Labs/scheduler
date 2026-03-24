"""LLM-as-judge for draft composer evals.

Evaluates generated drafts against golden responses on 5 behavioral
dimensions: correctness, tone, sign-off, recipients, and timezone handling.
Single Anthropic API call per eval case with structured JSON output.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor

from anthropic import Anthropic

JUDGE_MODEL = "claude-sonnet-4-6"

JUDGE_SYSTEM_PROMPT = """\
You are an eval judge for an AI email scheduling assistant. You evaluate \
generated draft emails against a golden (reference) response.

You will receive:
1. The email thread (conversation history)
2. The golden response (human-written ideal reply)
3. The generated draft (AI-produced reply)
4. The eval notes describing what this test case specifically checks

Evaluate the generated draft on these 5 criteria (each is binary pass/fail):

**correctness** — Does the draft handle the scheduling intent correctly?
- Proposes a reasonable time that respects the calendar
- Never re-suggests a time that was explicitly declined
- Handles reschedules, confirmations, and cancellations appropriately
- If the golden response proposes a specific time, the draft should propose \
a similarly reasonable time (not necessarily identical)

**tone** — Is the draft warm, natural, and professional?
- Not passive-aggressive (e.g., "as I mentioned", "I'm not sure what you mean")
- Not robotic or overly formal
- Appropriately concise — not verbose or over-explaining
- Matches the conversational register of the thread

**signoff** — Does the draft sign off as the correct person?
- Must sign off as the user (the person whose email account this is)
- Must NOT sign off as another participant in the thread

**recipients** — Are the To and CC fields correct?
- Reply goes to the right person (typically the last sender)
- All relevant CCs are preserved from the thread
- The user's own email is NOT in the CC
- No one is dropped or incorrectly added

**timezone** — Are times handled correctly with respect to timezones?
- Times include explicit timezone (e.g., "2pm PT", not just "2pm")
- Cross-timezone conversions are correct
- When sender's timezone is ambiguous, the draft clarifies or handles gracefully

Respond with ONLY a JSON object (no markdown, no explanation outside the JSON):
{
  "correctness": {"pass": true/false, "reason": "brief explanation"},
  "tone": {"pass": true/false, "reason": "brief explanation"},
  "signoff": {"pass": true/false, "reason": "brief explanation"},
  "recipients": {"pass": true/false, "reason": "brief explanation"},
  "timezone": {"pass": true/false, "reason": "brief explanation"},
  "summary": "1-sentence overall assessment"
}
"""


def _build_judge_prompt(result: dict) -> str:
    """Build the user prompt for the judge from a draft eval result."""
    messages = result.get("messages", [])
    trigger_idx = result.get("trigger_message_index", len(messages) - 1)

    # Format the email thread
    thread_lines = []
    for i, msg in enumerate(messages):
        marker = " ← TRIGGER" if i == trigger_idx else ""
        thread_lines.append(
            f"--- Message {i + 1}{marker} ---\n"
            f"From: {msg.get('sender', '')}\n"
            f"To: {msg.get('recipient', '')}\n"
            f"CC: {msg.get('cc', '') or '(none)'}\n"
            f"Date: {msg.get('date', '')}\n"
            f"Subject: {msg.get('subject', '')}\n\n"
            f"{msg.get('body', '')}"
        )
    thread_text = "\n\n".join(thread_lines)

    # Golden response
    golden = result.get("golden_response", {})
    golden_text = (
        f"To: {golden.get('recipient', '(not specified)')}\n"
        f"CC: {golden.get('cc', '(not specified)')}\n\n"
        f"{golden.get('body', '(no golden response)')}"
    )

    # Generated draft
    draft = result.get("draft") or {}
    if draft:
        draft_text = (
            f"To: {draft.get('to', '(not set)')}\n"
            f"CC: {draft.get('cc', '') or '(none)'}\n\n"
            f"{draft.get('body', '(empty body)')}"
        )
    else:
        draft_text = "(no draft was generated)"

    # Eval notes — pulled from the golden_response or the eval case itself
    notes = result.get("notes", "")

    return (
        f"## Email Thread\n\n{thread_text}\n\n"
        f"## Golden Response (reference)\n\n{golden_text}\n\n"
        f"## Generated Draft (to evaluate)\n\n{draft_text}\n\n"
        f"## Eval Notes\n\n{notes or 'No specific notes for this case.'}\n\n"
        f"## User Email\n\n{result.get('user_email', 'henry@ferganalabs.com')}\n\n"
        f"Judge the generated draft against the golden response now."
    )


def judge_draft(result: dict) -> dict:
    """Judge a single draft eval result. Returns verdict dict."""
    if "golden_response" not in result:
        return {"skipped": True, "reason": "no golden response"}

    client = Anthropic()
    prompt = _build_judge_prompt(result)

    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=1024,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Parse JSON — handle possible markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse judge response",
            "raw_response": raw,
        }

    criteria = ["correctness", "tone", "signoff", "recipients", "timezone"]
    passed = sum(1 for c in criteria if verdict.get(c, {}).get("pass", False))

    return {
        "eval_id": result.get("eval_id", ""),
        "verdict": "PASS" if passed == len(criteria) else "FAIL",
        "score": passed,
        "max_score": len(criteria),
        "criteria": {c: verdict.get(c, {"pass": False, "reason": "missing"}) for c in criteria},
        "summary": verdict.get("summary", ""),
    }


def judge_draft_evals(results: list[dict]) -> list[dict]:
    """Judge all draft eval results in parallel. Returns list of verdicts."""
    judgeable = [r for r in results if "golden_response" in r]
    if not judgeable:
        return []

    print(f"  Judging {len(judgeable)} draft evals...", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=min(len(judgeable), 10)) as pool:
        futures = [pool.submit(judge_draft, r) for r in judgeable]
        verdicts = [f.result() for f in futures]

    passed = sum(1 for v in verdicts if v.get("verdict") == "PASS")
    print(f"  Judge: {passed}/{len(verdicts)} PASS", file=sys.stderr)

    return verdicts
