"""Eval CLI — record your inbox once, then replay for deterministic evals.

Usage:
    # Step 1: Dump inbox + calendar to a fixture (run once, no LLM calls)
    python -m scheduler.eval record --out fixture.json --thread-ids t1 t2 t3

    # Step 2: Run evals against the frozen fixture (no API access)
    python -m scheduler.eval guides --fixture fixture.json
    python -m scheduler.eval draft --fixture fixture.json --thread-ids t1
    python -m scheduler.eval classify --fixture fixture.json --thread-ids t1
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _resolve_thread_ids(args) -> list[str]:
    """Resolve thread IDs: CLI flag > eval config > empty."""
    if args.thread_ids:
        return args.thread_ids
    from scheduler.eval.config import EVAL_CASES
    return [c.thread_id for c in EVAL_CASES]


def _get_eval_case(thread_id: str):
    """Look up the EvalCase for a thread ID, or None."""
    from scheduler.eval.config import EVAL_CASES
    for case in EVAL_CASES:
        if case.thread_id == thread_id:
            return case
    return None


def cmd_record(args):
    """Dump the last 1000 emails + calendar + guides to a fixture. No LLM calls."""
    from datetime import datetime, timedelta

    from scheduler.auth.google_auth import get_credentials
    from scheduler.calendar.client import CalendarClient
    from scheduler.config import config
    from scheduler.eval.backends import _serialize_email, _serialize_event, save_fixture
    from scheduler.gmail.client import GmailClient

    creds = get_credentials()
    gmail = GmailClient(creds)
    calendar = CalendarClient(creds, config.stash_calendar_name)

    # 1. Fetch last 1000 emails (everything the guide agents could see)
    lookback_days = config.onboarding_lookback_days
    query = f"newer_than:{lookback_days}d"
    print(f"Fetching emails from the last {lookback_days} days (up to 1000)...", file=sys.stderr)
    emails = gmail.search(query=query, max_results=1000)
    messages = [_serialize_email(e) for e in emails]
    seen_message_ids = {m["id"] for m in messages}
    print(f"  {len(messages)} emails fetched", file=sys.stderr)

    # 2. Fetch full threads so read_thread replays are complete
    import time
    from scheduler.eval.config import EVAL_CASES

    seen_thread_ids = {m["thread_id"] for m in messages}
    all_thread_ids = list(seen_thread_ids)
    for tid in (args.thread_ids or []) + [c.thread_id for c in EVAL_CASES]:
        if tid not in seen_thread_ids:
            all_thread_ids.append(tid)
            seen_thread_ids.add(tid)

    print(f"Reading {len(all_thread_ids)} threads...", file=sys.stderr)
    for i, tid in enumerate(all_thread_ids):
        for attempt in range(3):
            try:
                thread_messages = gmail.get_thread(tid)
                for m in thread_messages:
                    if m.id not in seen_message_ids:
                        messages.append(_serialize_email(m))
                        seen_message_ids.add(m.id)
                break
            except Exception as e:
                print(f"  Thread {tid} attempt {attempt + 1} failed: {type(e).__name__}: {e}", file=sys.stderr)
                if attempt < 2:
                    time.sleep(2)

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(all_thread_ids)} threads...", file=sys.stderr)

    print(f"  {len(messages)} total messages", file=sys.stderr)

    # 4. Calendar: lookback + 30 days ahead
    now = datetime.now()
    cal_start = now - timedelta(days=lookback_days)
    cal_end = now + timedelta(days=30)
    print("Fetching calendar events...", file=sys.stderr)
    raw_events = calendar.get_all_events(cal_start, cal_end, include_primary=True)
    events = [_serialize_event(e) for e in raw_events]
    print(f"  {len(events)} calendar events", file=sys.stderr)

    # 5. Timezone
    tz = calendar.get_user_timezone()

    # 6. Guides (if they exist)
    from scheduler.guides import load_guide
    guides = {}
    for name in ["scheduling_preferences", "email_style"]:
        guides[name] = load_guide(name)

    # 7. Save
    metadata = {
        "thread_ids": [c.thread_id for c in EVAL_CASES] + (args.thread_ids or []),
        "lookback_days": lookback_days,
        "n_messages": len(messages),
        "n_events": len(events),
        "calendar_window": {"start": cal_start.isoformat(), "end": cal_end.isoformat()},
    }
    save_fixture(args.out, messages=messages, events=events, timezone=tz, guides=guides, metadata=metadata)
    print(f"Saved fixture to {args.out}", file=sys.stderr)


def _load_canonical_classifier_evals() -> list[dict]:
    """Load canonical classifier eval cases from the JSON file."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evals", "classifier_canonical_evals.json")
    path = os.path.normpath(path)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def cmd_classify(args):
    """Run the classifier on specific messages from the fixture."""
    from scheduler.classifier.intent import classify_email
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)

    # Index messages by id and group by thread
    messages_by_id: dict[str, dict] = {}
    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        messages_by_id[msg["id"]] = msg
        threads.setdefault(msg["thread_id"], []).append(msg)

    # Build list of (message_to_classify, eval_metadata) pairs
    eval_targets: list[tuple[dict, dict | None]] = []

    if args.thread_ids:
        # Ad-hoc mode: classify latest message in each thread, no expected values
        for tid in args.thread_ids:
            thread_msgs = threads.get(tid, [])
            if not thread_msgs:
                print(f"Thread {tid} not found in fixture, skipping", file=sys.stderr)
                continue
            eval_targets.append((thread_msgs[-1], None))
    else:
        # Canonical mode: load eval cases with message_id targeting
        canonical = _load_canonical_classifier_evals()
        if not canonical:
            print("No canonical evals found and no --thread-ids specified.", file=sys.stderr)
            sys.exit(1)
        for case in canonical:
            msg_id = case.get("message_id")
            if msg_id and msg_id in messages_by_id:
                eval_targets.append((messages_by_id[msg_id], case))
            else:
                # Fallback: latest message in thread
                thread_msgs = threads.get(case["thread_id"], [])
                if thread_msgs:
                    eval_targets.append((thread_msgs[-1], case))
                else:
                    print(f"Message {msg_id} / thread {case['thread_id']} not in fixture, skipping", file=sys.stderr)

    results = []
    for msg, case in eval_targets:
        c = classify_email(msg["subject"], msg["body"], msg["sender"])

        result = {
            "thread_id": msg["thread_id"],
            "message_id": msg["id"],
            "description": case.get("description", "") if case else "",
            "intent": c.intent.value,
            "confidence": c.confidence,
            "summary": c.summary,
            "proposed_times": c.proposed_times,
            "participants": c.participants,
            "duration_minutes": c.duration_minutes,
            "is_sales_email": c.is_sales_email,
        }

        if case:
            expected_intent = case["expected_classification"].lower()
            result["expected_intent"] = expected_intent
            result["intent_match"] = c.intent.value == expected_intent
            expected_is_sales = case.get("expected_is_sales", False)
            result["expected_is_sales"] = expected_is_sales
            result["is_sales_match"] = c.is_sales_email == expected_is_sales

        results.append(result)

    # Print results
    print(json.dumps(results, indent=2))

    # Print summary
    cases_with_expected = [r for r in results if "intent_match" in r]
    if cases_with_expected:
        passed = sum(1 for r in cases_with_expected if r["intent_match"])
        total = len(cases_with_expected)
        print(f"\n--- Classifier: {passed}/{total} intent matches ---", file=sys.stderr)
        for r in cases_with_expected:
            status = "PASS" if r["intent_match"] else "FAIL"
            print(f"  {status}  {r['description']:40s}  got={r['intent']:25s}  expected={r['expected_intent']}", file=sys.stderr)


def cmd_draft(args):
    """Run the draft composer against a thread from the fixture."""
    from scheduler.classifier.intent import classify_email
    from scheduler.drafts.composer import DraftComposer
    from scheduler.eval.backends import ReplayDraftBackend, load_fixture

    fixture = load_fixture(args.fixture)

    # Group messages by thread
    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        threads.setdefault(msg["thread_id"], []).append(msg)

    thread_ids = _resolve_thread_ids(args)
    if not thread_ids:
        print("No thread IDs specified. Add them to eval/config.py or pass --thread-ids.", file=sys.stderr)
        sys.exit(1)

    results = []
    for tid in thread_ids:
        messages = threads.get(tid, [])
        if not messages:
            print(f"Thread {tid} not found in fixture, skipping", file=sys.stderr)
            continue

        latest = messages[-1]
        c = classify_email(latest["subject"], latest["body"], latest["sender"])
        classification = {
            "intent": c.intent.value,
            "confidence": c.confidence,
            "summary": c.summary,
            "proposed_times": c.proposed_times,
            "participants": c.participants,
            "duration_minutes": c.duration_minutes,
        }

        case = _get_eval_case(tid)
        user_email = case.user_email if case else "henry@ferganalabs.com"

        backend = ReplayDraftBackend(fixture)
        composer = DraftComposer(backend, user_id="eval", user_email=user_email)
        composer.compose_and_create_draft(latest, classification, current_datetime=latest["date"])

        result = {
            "thread_id": tid,
            "description": case.description if case else "",
            "classification": classification,
            "draft": backend.captured_draft,
            "sent": backend.captured_sent,
            "calendar_events": backend.captured_events,
        }

        if case:
            result["expected_draft"] = case.expected_draft

        results.append(result)

    # Print results
    print(json.dumps(results, indent=2))

    # Print summary
    cases_with_expected = [r for r in results if "expected_draft" in r]
    if cases_with_expected:
        print("\n--- Draft eval summary ---", file=sys.stderr)
        for r in cases_with_expected:
            desc = r.get("description") or r["thread_id"]
            draft_body = (r.get("draft") or {}).get("body")
            print(f"\n  {desc}:", file=sys.stderr)
            print(f"    Expected: {r['expected_draft']}", file=sys.stderr)
            print(f"    Got:      {draft_body}", file=sys.stderr)
            for check in r["checks"]:
                status = "PASS" if check["passed"] else "FAIL"
                print(f"    {status}: {check['check']}", file=sys.stderr)


def cmd_guides(args):
    """Run guide-writer agents against the fixture."""
    import anyio
    from scheduler.eval.backends import ReplayGuideBackend, load_fixture
    from scheduler.guides.preferences import run_preferences_agent
    from scheduler.guides.style import run_style_agent

    fixture = load_fixture(args.fixture)
    backend = ReplayGuideBackend(fixture)

    async def _run():
        async with anyio.create_task_group() as tg:
            tg.start_soon(run_preferences_agent, backend)
            tg.start_soon(run_style_agent, backend)

    anyio.run(_run)

    print(json.dumps(backend.captured_guides, indent=2))


def cmd_list(args):
    """List all threads in a fixture so you can pick eval thread IDs."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)

    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        threads.setdefault(msg["thread_id"], []).append(msg)

    # Sort threads by latest message date (newest first)
    sorted_threads = sorted(
        threads.items(),
        key=lambda item: item[1][-1].get("date", ""),
        reverse=True,
    )

    for tid, msgs in sorted_threads:
        latest = msgs[-1]
        subject = (latest.get("subject") or "(no subject)")[:60]
        sender = (latest.get("sender") or "")[:40]
        date = (latest.get("date") or "")[:10]
        n = len(msgs)
        print(f"  {tid}  {date}  {n:2d} msgs  {sender:40s}  {subject}")


def main():
    parser = argparse.ArgumentParser(description="Eval CLI for scheduler agents")
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Dump inbox + calendar to a fixture (run once)")
    rec.add_argument("--out", required=True, help="Output fixture file path")
    rec.add_argument("--thread-ids", nargs="*", help="Extra thread IDs to include for draft eval")
    rec.set_defaults(func=cmd_record)

    lst = sub.add_parser("list", help="List all threads in a fixture")
    lst.add_argument("--fixture", required=True, help="Fixture file")
    lst.set_defaults(func=cmd_list)

    cls = sub.add_parser("classify", help="Run classifier on thread(s) from a fixture")
    cls.add_argument("--fixture", required=True, help="Fixture file")
    cls.add_argument("--thread-ids", nargs="*", help="Thread IDs (default: EVAL_THREADS from config)")
    cls.set_defaults(func=cmd_classify)

    dft = sub.add_parser("draft", help="Run draft composer on thread(s) from a fixture")
    dft.add_argument("--fixture", required=True, help="Fixture file")
    dft.add_argument("--thread-ids", nargs="*", help="Thread IDs (default: EVAL_THREADS from config)")
    dft.set_defaults(func=cmd_draft)

    gd = sub.add_parser("guides", help="Run guide-writer agents against a fixture")
    gd.add_argument("--fixture", required=True, help="Fixture file")
    gd.set_defaults(func=cmd_guides)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
