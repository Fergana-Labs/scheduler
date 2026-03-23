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
import sys


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
    print(f"  {len(messages)} emails fetched", file=sys.stderr)

    # 2. Read full threads for every email we found
    thread_ids = list({m["thread_id"] for m in messages})
    print(f"Reading {len(thread_ids)} unique threads...", file=sys.stderr)
    seen_message_ids = {m["id"] for m in messages}
    for tid in thread_ids:
        thread_messages = gmail.get_thread(tid)
        for m in thread_messages:
            if m.id not in seen_message_ids:
                messages.append(_serialize_email(m))
                seen_message_ids.add(m.id)

    # 3. Also fetch any extra threads passed via --thread-ids
    extra_thread_ids = set(args.thread_ids or []) - set(thread_ids)
    if extra_thread_ids:
        print(f"Reading {len(extra_thread_ids)} additional thread(s)...", file=sys.stderr)
        for tid in extra_thread_ids:
            thread_messages = gmail.get_thread(tid)
            for m in thread_messages:
                if m.id not in seen_message_ids:
                    messages.append(_serialize_email(m))
                    seen_message_ids.add(m.id)

    print(f"  {len(messages)} total messages across {len(thread_ids) + len(extra_thread_ids)} threads", file=sys.stderr)

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
        "thread_ids": args.thread_ids or [],
        "lookback_days": lookback_days,
        "n_messages": len(messages),
        "n_threads": len(thread_ids) + len(extra_thread_ids),
        "n_events": len(events),
        "calendar_window": {"start": cal_start.isoformat(), "end": cal_end.isoformat()},
    }
    save_fixture(args.out, messages=messages, events=events, timezone=tz, guides=guides, metadata=metadata)
    print(f"Saved fixture to {args.out}", file=sys.stderr)


def cmd_classify(args):
    """Run the classifier on a thread from the fixture."""
    from scheduler.classifier.intent import classify_email
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)

    # Group messages by thread
    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        threads.setdefault(msg["thread_id"], []).append(msg)

    thread_ids = args.thread_ids or fixture.get("metadata", {}).get("thread_ids", [])
    if not thread_ids:
        print("No thread IDs specified and none found in fixture metadata", file=sys.stderr)
        sys.exit(1)

    results = []
    for tid in thread_ids:
        messages = threads.get(tid, [])
        if not messages:
            print(f"Thread {tid} not found in fixture, skipping", file=sys.stderr)
            continue

        latest = messages[-1]
        c = classify_email(latest["subject"], latest["body"], latest["sender"])
        results.append({
            "thread_id": tid,
            "intent": c.intent.value,
            "confidence": c.confidence,
            "summary": c.summary,
            "proposed_times": c.proposed_times,
            "participants": c.participants,
            "duration_minutes": c.duration_minutes,
            "is_sales_email": c.is_sales_email,
        })

    print(json.dumps(results, indent=2))


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

    thread_ids = args.thread_ids or fixture.get("metadata", {}).get("thread_ids", [])
    if not thread_ids:
        print("No thread IDs specified and none found in fixture metadata", file=sys.stderr)
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

        backend = ReplayDraftBackend(fixture)
        composer = DraftComposer(backend, user_id="eval", user_email="eval@test.com")
        composer.compose_and_create_draft(latest, classification)

        results.append({
            "thread_id": tid,
            "classification": classification,
            "draft": backend.captured_draft,
            "sent": backend.captured_sent,
            "calendar_events": backend.captured_events,
        })

    print(json.dumps(results, indent=2))


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


def main():
    parser = argparse.ArgumentParser(description="Eval CLI for scheduler agents")
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Dump inbox + calendar to a fixture (run once)")
    rec.add_argument("--out", required=True, help="Output fixture file path")
    rec.add_argument("--thread-ids", nargs="*", help="Extra thread IDs to include for draft eval")
    rec.set_defaults(func=cmd_record)

    cls = sub.add_parser("classify", help="Run classifier on thread(s) from a fixture")
    cls.add_argument("--fixture", required=True, help="Fixture file")
    cls.add_argument("--thread-ids", nargs="*", help="Thread IDs to classify (default: all from metadata)")
    cls.set_defaults(func=cmd_classify)

    dft = sub.add_parser("draft", help="Run draft composer on thread(s) from a fixture")
    dft.add_argument("--fixture", required=True, help="Fixture file")
    dft.add_argument("--thread-ids", nargs="*", help="Thread IDs to draft (default: all from metadata)")
    dft.set_defaults(func=cmd_draft)

    gd = sub.add_parser("guides", help="Run guide-writer agents against a fixture")
    gd.add_argument("--fixture", required=True, help="Fixture file")
    gd.set_defaults(func=cmd_guides)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
