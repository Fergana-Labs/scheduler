"""Eval CLI — record your inbox once, then replay for deterministic evals.

Usage:
    # Step 1: Dump inbox + calendar to a fixture (run once, no LLM calls)
    python -m scheduler.eval record --out fixture.json --thread-ids t1 t2 t3

    # Step 2: Run all evals end-to-end (guides -> onboard -> classify -> draft -> reasoning)
    python -m scheduler.eval run --fixture fixture.json --out evals/results/run.json

    # Or run individual evals:
    python -m scheduler.eval guides --fixture fixture.json
    python -m scheduler.eval draft --fixture fixture.json --thread-ids t1
    python -m scheduler.eval reasoning --fixture fixture.json --thread-ids t1
    python -m scheduler.eval classify --fixture fixture.json --thread-ids t1
    python -m scheduler.eval onboard --fixture fixture.json
    python -m scheduler.eval lifecycle --fixture fixture.json --runs 3

    # Guide updater eval (add 'updater_diffs' key to fixture to test):
    python -m scheduler.eval updater --fixture fixture.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# Reusable eval runners (return results, no printing)
# ---------------------------------------------------------------------------

def run_guides_eval(fixture: dict) -> dict[str, str]:
    """Run guide-writer agents against the fixture. Returns {name: content}."""
    import anyio
    from scheduler.eval.backends import ReplayGuideBackend
    from scheduler.guides.preferences import run_preferences_agent
    from scheduler.guides.style import run_style_agent

    backend = ReplayGuideBackend(fixture)

    async def _run():
        async with anyio.create_task_group() as tg:
            tg.start_soon(run_preferences_agent, backend)
            tg.start_soon(run_style_agent, backend)

    anyio.run(_run)
    return backend.captured_guides


def run_onboard_eval(fixture: dict, lookback_days: int = 60) -> list[dict]:
    """Run the onboarding agent against the fixture. Returns list of events added."""
    from scheduler.eval.backends import ReplayBackfillBackend
    from scheduler.onboarding.agent import run_backfill_agent

    backend = ReplayBackfillBackend(fixture)
    run_backfill_agent(backend, lookback_days)
    return backend.captured_events


def run_classify_eval(fixture: dict, thread_ids: list[str] | None = None) -> list[dict]:
    """Run the classifier eval. Returns list of result dicts."""
    from scheduler.classifier.intent import classify_email

    messages_by_id: dict[str, dict] = {}
    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        messages_by_id[msg["id"]] = msg
        threads.setdefault(msg["thread_id"], []).append(msg)

    eval_targets: list[tuple[dict, dict | None]] = []

    if thread_ids:
        for tid in thread_ids:
            thread_msgs = threads.get(tid, [])
            if not thread_msgs:
                print(f"Thread {tid} not found in fixture, skipping", file=sys.stderr)
                continue
            eval_targets.append((thread_msgs[-1], None))
    else:
        canonical = _load_canonical_classifier_evals()
        if not canonical:
            print("No canonical evals found and no thread_ids specified.", file=sys.stderr)
            return []
        for case in canonical:
            msg_id = case.get("message_id")
            if msg_id and msg_id in messages_by_id:
                eval_targets.append((messages_by_id[msg_id], case))
            else:
                thread_msgs = threads.get(case["thread_id"], [])
                if thread_msgs:
                    eval_targets.append((thread_msgs[-1], case))
                else:
                    print(f"Message {msg_id} / thread {case['thread_id']} not in fixture, skipping", file=sys.stderr)

    results = []
    for msg, case in eval_targets:
        thread_msgs = threads.get(msg["thread_id"], [])
        msg_idx = next((i for i, m in enumerate(thread_msgs) if m["id"] == msg["id"]), len(thread_msgs))
        prior = [
            {"sender": m["sender"], "body": m["body"], "date": m.get("date", "")}
            for m in thread_msgs[:msg_idx]
        ]

        c = classify_email(
            msg["subject"], msg["body"], msg["sender"],
            thread_messages=prior,
            recipient=msg.get("recipient", ""), cc=msg.get("cc", ""),
        )

        result = {
            "thread_id": msg["thread_id"],
            "message_id": msg["id"],
            "description": case.get("description", "") if case else "",
            "subject": msg.get("subject", ""),
            "sender": msg.get("sender", ""),
            "body": msg.get("body", ""),
            "intent": c.intent.value,
            "confidence": c.confidence,
            "summary": c.summary,
            "proposed_times": c.proposed_times,
            "participants": c.participants,
            "duration_minutes": c.duration_minutes,
            "is_sales_email": c.is_sales_email,
        }

        if case:
            raw_expected = case["expected_classification"].lower()
            expected_intent = "doesnt_need_draft" if raw_expected == "not_scheduling" else "needs_draft"
            result["expected_intent"] = expected_intent
            result["intent_match"] = c.intent.value == expected_intent
            expected_is_sales = case.get("expected_is_sales", False)
            result["expected_is_sales"] = expected_is_sales
            result["is_sales_match"] = c.is_sales_email == expected_is_sales

        results.append(result)

    return results


def run_draft_eval(fixture: dict, thread_ids: list[str] | None = None) -> list[dict]:
    """Run the draft composer eval. Returns list of result dicts."""
    from scheduler.classifier.intent import classify_email
    from scheduler.drafts.composer import DraftComposer
    from scheduler.eval.backends import ReplayDraftBackend

    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        threads.setdefault(msg["thread_id"], []).append(msg)

    eval_targets: list[tuple[dict, list[dict], int, dict | None]] = []

    if thread_ids:
        for tid in thread_ids:
            thread_msgs = threads.get(tid, [])
            if not thread_msgs:
                print(f"Thread {tid} not found in fixture, skipping", file=sys.stderr)
                continue
            eval_targets.append((thread_msgs[-1], thread_msgs, len(thread_msgs) - 1, None))
    else:
        canonical = _load_canonical_draft_evals()
        if not canonical:
            print("No canonical draft evals found and no thread_ids specified.", file=sys.stderr)
            return []
        for case in canonical:
            trigger_idx = case["trigger_message_index"]
            case_msgs = case["messages"]
            if trigger_idx >= len(case_msgs):
                print(f"Trigger index {trigger_idx} out of range for {case['eval_id']}, skipping", file=sys.stderr)
                continue
            trigger = case_msgs[trigger_idx]
            eval_targets.append((trigger, case_msgs, trigger_idx, case))

    def _run_single_draft(trigger, thread_msgs, trigger_idx, case):
        prior = [
            {"sender": m["sender"], "body": m["body"], "date": m.get("date", "")}
            for m in thread_msgs[:trigger_idx]
        ]
        c = classify_email(
            trigger["subject"], trigger["body"], trigger["sender"],
            thread_messages=prior,
            recipient=trigger.get("recipient", ""), cc=trigger.get("cc", ""),
        )
        classification = {
            "intent": c.intent.value,
            "confidence": c.confidence,
            "summary": c.summary,
            "proposed_times": c.proposed_times,
            "participants": c.participants,
            "duration_minutes": c.duration_minutes,
        }

        user_email = case["user_email"] if case and "user_email" in case else "henry@ferganalabs.com"

        scoped_messages = thread_msgs[: trigger_idx + 1]
        scoped_fixture = {
            "messages": scoped_messages,
            "events": fixture.get("events", []),
            "timezone": fixture.get("timezone", "UTC"),
            "guides": fixture.get("guides", {}),
        }

        backend = ReplayDraftBackend(scoped_fixture)
        composer = DraftComposer(backend, user_id="eval", user_email=user_email)
        eval_datetime = (case.get("current_datetime") if case else None) or trigger["date"]
        composer.compose_and_create_draft(trigger, classification, current_datetime=eval_datetime)

        eval_id = case["eval_id"] if case else trigger.get("thread_id", "")
        print(f"  Draft done: {eval_id}", file=sys.stderr)

        result = {
            "eval_id": eval_id,
            "thread_id": trigger.get("thread_id", ""),
            "subject": case.get("subject", trigger.get("subject", "")) if case else trigger.get("subject", ""),
            "messages": thread_msgs,
            "trigger_message_index": trigger_idx,
            "user_email": user_email,
            "current_datetime": eval_datetime,
            "classification": classification,
            "draft": backend.captured_draft,
            "sent": backend.captured_sent,
        }

        if case and "golden_response" in case:
            result["golden_response"] = case["golden_response"]

        return result

    # Run all draft evals in parallel (each gets its own thread/event loop)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(eval_targets) or 1) as pool:
        futures = [
            pool.submit(_run_single_draft, trigger, thread_msgs, trigger_idx, case)
            for trigger, thread_msgs, trigger_idx, case in eval_targets
        ]
        results = [f.result() for f in futures]

    return results


def run_reasoning_eval(fixture: dict, thread_ids: list[str] | None = None) -> list[dict]:
    """Run reasoning email eval. Returns list of result dicts.

    Reuses the same canonical draft eval cases — every thread that gets a
    draft also gets a reasoning email in prod.
    """
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta, timezone as tz

    from scheduler.calendar.client import Event
    from scheduler.classifier.intent import classify_email
    from scheduler.eval.backends import _filter_events
    from scheduler.lifecycle.reasoning import _parse_dates, build_reasoning_body

    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        threads.setdefault(msg["thread_id"], []).append(msg)

    eval_targets: list[tuple[dict, list[dict], int, dict | None]] = []

    if thread_ids:
        for tid in thread_ids:
            thread_msgs = threads.get(tid, [])
            if not thread_msgs:
                print(f"Thread {tid} not found in fixture, skipping", file=sys.stderr)
                continue
            eval_targets.append((thread_msgs[-1], thread_msgs, len(thread_msgs) - 1, None))
    else:
        canonical = _load_canonical_draft_evals()
        if not canonical:
            print("No canonical draft evals found and no thread_ids specified.", file=sys.stderr)
            return []
        for case in canonical:
            trigger_idx = case["trigger_message_index"]
            case_msgs = case["messages"]
            if trigger_idx >= len(case_msgs):
                continue
            eval_targets.append((case_msgs[trigger_idx], case_msgs, trigger_idx, case))

    def _run_single(trigger, thread_msgs, trigger_idx, case):
        prior = [
            {"sender": m["sender"], "body": m["body"], "date": m.get("date", "")}
            for m in thread_msgs[:trigger_idx]
        ]
        c = classify_email(
            trigger["subject"], trigger["body"], trigger["sender"],
            thread_messages=prior,
            recipient=trigger.get("recipient", ""), cc=trigger.get("cc", ""),
        )
        classification = {
            "intent": c.intent.value,
            "confidence": c.confidence,
            "summary": c.summary,
            "proposed_times": c.proposed_times,
            "participants": c.participants,
            "duration_minutes": c.duration_minutes,
        }

        dates = _parse_dates(c.proposed_times)
        # Make dates timezone-aware (UTC) so they compare with fixture events
        aware_dates = [
            d.replace(tzinfo=tz.utc) if d.tzinfo is None else d
            for d in dates
        ]
        day_start = min(aware_dates).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = max(aware_dates).replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(seconds=1)
        fixture_events = _filter_events(
            fixture.get("events", []),
            day_start.isoformat(),
            day_end.isoformat(),
        )

        # Convert fixture event dicts to Event objects for build_reasoning_body
        events = [
            Event(
                id=ev.get("id"),
                summary=ev.get("summary", ""),
                start=datetime.fromisoformat(ev["start"]),
                end=datetime.fromisoformat(ev["end"]),
                description=ev.get("description", ""),
                source=ev.get("source", ""),
            )
            for ev in fixture_events
        ]

        reasoning_body = build_reasoning_body(c, events)

        eval_id = case["eval_id"] if case else trigger.get("thread_id", "")
        print(f"  Reasoning done: {eval_id}", file=sys.stderr)

        return {
            "eval_id": eval_id,
            "thread_id": trigger.get("thread_id", ""),
            "subject": case.get("subject", "") if case else trigger.get("subject", ""),
            "messages": thread_msgs,
            "trigger_message_index": trigger_idx,
            "user_email": case.get("user_email", "henry@ferganalabs.com") if case else "henry@ferganalabs.com",
            "classification": classification,
            "reasoning_body": reasoning_body,
            "calendar_events_used": fixture_events,
        }

    with ThreadPoolExecutor(max_workers=len(eval_targets) or 1) as pool:
        futures = [
            pool.submit(_run_single, trigger, thread_msgs, trigger_idx, case)
            for trigger, thread_msgs, trigger_idx, case in eval_targets
        ]
        results = [f.result() for f in futures]

    return results


def run_lifecycle_eval(fixture: dict, n_runs: int = 3) -> list[dict]:
    """Run the lifecycle (welcome email + draft reply) eval.

    Generates `n_runs` independent welcome + draft pairs using the fixture's
    guides and calendar. Each run is an independent sample so the judge can
    catch intermittent creepiness.
    """
    from concurrent.futures import ThreadPoolExecutor

    from scheduler.lifecycle.welcome import generate_draft_reply, generate_welcome_email

    scheduling_prefs = fixture.get("guides", {}).get("scheduling_preferences", "")
    email_style = fixture.get("guides", {}).get("email_style", "")

    if not scheduling_prefs or not email_style:
        print("  Lifecycle: missing guides, skipping", file=sys.stderr)
        return []

    # Build events_text from fixture calendar (next 14 days from latest message date)
    events = fixture.get("events", [])
    events_text = "\n".join(
        f"- {ev.get('summary', '')}: {ev.get('start', '')[:16]} – {ev.get('end', '')[:16]}"
        for ev in events[:30]  # cap at 30 to keep prompt reasonable
    ) or "No events in the next 14 days."

    user_email = "henry@ferganalabs.com"
    sender = "sam@tryscheduled.com"

    def _run_single(run_idx: int) -> dict:
        eval_id = f"lifecycle-run-{run_idx + 1}"
        try:
            welcome_data = generate_welcome_email(user_email, scheduling_prefs, email_style)
            subject = welcome_data.get("subject", "")
            welcome_body = welcome_data.get("body", "")
        except Exception as e:
            print(f"  {eval_id}: welcome email failed: {e}", file=sys.stderr)
            return {"eval_id": eval_id, "error": f"welcome generation failed: {e}"}

        try:
            draft_body = generate_draft_reply(
                sender, subject, welcome_body,
                email_style, scheduling_prefs, events_text,
            )
        except Exception as e:
            print(f"  {eval_id}: draft reply failed: {e}", file=sys.stderr)
            draft_body = None

        print(f"  {eval_id}: done", file=sys.stderr)
        return {
            "eval_id": eval_id,
            "user_email": user_email,
            "scheduling_prefs": scheduling_prefs,
            "email_style": email_style,
            "calendar_events": events[:30],
            "welcome_email": {"subject": subject, "body": welcome_body},
            "draft_reply": draft_body,
        }

    with ThreadPoolExecutor(max_workers=n_runs) as pool:
        futures = [pool.submit(_run_single, i) for i in range(n_runs)]
        results = [f.result() for f in futures]

    return results


# ---------------------------------------------------------------------------
# Unified run command
# ---------------------------------------------------------------------------

def cmd_run(args):
    """Run all evals end-to-end: guides + onboard + classify in parallel, then draft."""
    from concurrent.futures import ThreadPoolExecutor
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    lookback_days = args.lookback_days or 60

    # Phase 1: guides + onboard + classify in parallel
    # (each in its own thread because guides/onboard call anyio.run internally)
    print("Phase 1: Running guides + onboard + classify in parallel...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_guides = pool.submit(run_guides_eval, fixture)
        future_onboard = pool.submit(run_onboard_eval, fixture, lookback_days)
        future_classify = pool.submit(run_classify_eval, fixture)

    guides = future_guides.result()
    print(f"  Guides done: {', '.join(guides.keys())}", file=sys.stderr)

    onboard_events = future_onboard.result()
    print(f"  Onboard done: {len(onboard_events)} calendar events", file=sys.stderr)

    classify_results = future_classify.result()
    cases_with_expected = [r for r in classify_results if "intent_match" in r]
    if cases_with_expected:
        passed = sum(1 for r in cases_with_expected if r["intent_match"])
        print(f"  Classify done: {passed}/{len(cases_with_expected)} intent matches", file=sys.stderr)
    else:
        print(f"  Classify done: {len(classify_results)} results", file=sys.stderr)

    # Phase 2: draft + reasoning + lifecycle evals in parallel (all use patched fixture)
    print("Phase 2: Running draft + reasoning + lifecycle evals (with generated guides + calendar)...", file=sys.stderr)
    patched = {
        **fixture,
        "guides": {**fixture.get("guides", {}), **guides},
        "events": fixture.get("events", []) + onboard_events,
    }
    n_lifecycle_runs = args.lifecycle_runs or 3
    with ThreadPoolExecutor(max_workers=3) as pool:
        future_draft = pool.submit(run_draft_eval, patched)
        future_reasoning = pool.submit(run_reasoning_eval, patched)
        future_lifecycle = pool.submit(run_lifecycle_eval, patched, n_lifecycle_runs)
        draft_results = future_draft.result()
        reasoning_results = future_reasoning.result()
        lifecycle_results = future_lifecycle.result()

    drafted = sum(1 for r in draft_results if r.get("draft"))
    print(f"  Drafts: {drafted}/{len(draft_results)} produced", file=sys.stderr)

    reasoned = sum(1 for r in reasoning_results if r.get("reasoning_body"))
    print(f"  Reasoning: {reasoned}/{len(reasoning_results)} produced", file=sys.stderr)

    lifecycle_ok = sum(1 for r in lifecycle_results if r.get("welcome_email"))
    print(f"  Lifecycle: {lifecycle_ok}/{len(lifecycle_results)} produced", file=sys.stderr)

    # Phase 3: LLM judges on draft + reasoning + lifecycle evals
    judge_verdicts = []
    reasoning_verdicts = []
    lifecycle_verdicts = []
    if not args.no_judge:
        from scheduler.eval.judge import judge_draft_evals, judge_lifecycle_evals, judge_reasoning_evals
        print("Phase 3: Running LLM judges on draft + reasoning + lifecycle evals...", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=3) as pool:
            future_draft_judge = pool.submit(judge_draft_evals, draft_results)
            future_reasoning_judge = pool.submit(judge_reasoning_evals, reasoning_results)
            future_lifecycle_judge = pool.submit(judge_lifecycle_evals, lifecycle_results)
            judge_verdicts = future_draft_judge.result()
            reasoning_verdicts = future_reasoning_judge.result()
            lifecycle_verdicts = future_lifecycle_judge.result()

        verdict_by_id = {v["eval_id"]: v for v in judge_verdicts if "eval_id" in v}
        for r in draft_results:
            if r.get("eval_id") in verdict_by_id:
                r["judge"] = verdict_by_id[r["eval_id"]]

        reasoning_verdict_by_id = {v["eval_id"]: v for v in reasoning_verdicts if "eval_id" in v}
        for r in reasoning_results:
            if r.get("eval_id") in reasoning_verdict_by_id:
                r["judge"] = reasoning_verdict_by_id[r["eval_id"]]

        lifecycle_verdict_by_id = {v["eval_id"]: v for v in lifecycle_verdicts if "eval_id" in v}
        for r in lifecycle_results:
            if r.get("eval_id") in lifecycle_verdict_by_id:
                r["judge"] = lifecycle_verdict_by_id[r["eval_id"]]

    results = {
        "metadata": {
            "fixture": args.fixture,
            "ran_at": datetime.now().isoformat(),
            "lookback_days": lookback_days,
            "n_classify": len(classify_results),
            "n_draft": len(draft_results),
            "n_reasoning": len(reasoning_results),
            "n_lifecycle": len(lifecycle_results),
            "n_onboard_events": len(onboard_events),
            "n_guides": len(guides),
            "n_judge": len(judge_verdicts),
            "n_reasoning_judge": len(reasoning_verdicts),
            "n_lifecycle_judge": len(lifecycle_verdicts),
        },
        "guides": guides,
        "onboard": onboard_events,
        "classify": classify_results,
        "draft": draft_results,
        "reasoning": reasoning_results,
        "lifecycle": lifecycle_results,
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved results to {args.out}", file=sys.stderr)
    print(f"Open evals/viewer.html and load this file to review.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Standalone subcommands (thin wrappers around the reusable functions)
# ---------------------------------------------------------------------------

def cmd_record(args):
    """Dump the last 1000 emails + calendar + guides to a fixture. No LLM calls."""
    from datetime import timedelta

    from scheduler.auth.google_auth import get_credentials
    from scheduler.calendar.client import CalendarClient
    from scheduler.config import config
    from scheduler.eval.backends import _serialize_email, _serialize_event, save_fixture
    from scheduler.gmail.client import GmailClient

    creds = get_credentials()
    gmail = GmailClient(creds)
    calendar = CalendarClient(creds, config.scheduled_calendar_name)

    lookback_days = config.onboarding_lookback_days
    query = f"newer_than:{lookback_days}d"
    print(f"Fetching emails from the last {lookback_days} days (up to 1000)...", file=sys.stderr)
    emails = gmail.search(query=query, max_results=1000)
    messages = [_serialize_email(e) for e in emails]
    seen_message_ids = {m["id"] for m in messages}
    print(f"  {len(messages)} emails fetched", file=sys.stderr)

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

    now = datetime.now()
    cal_start = now - timedelta(days=lookback_days)
    cal_end = now + timedelta(days=30)
    print("Fetching calendar events...", file=sys.stderr)
    raw_events = calendar.get_all_events(cal_start, cal_end, include_primary=True)
    events = [_serialize_event(e) for e in raw_events]
    print(f"  {len(events)} calendar events", file=sys.stderr)

    tz = calendar.get_user_timezone()

    from scheduler.guides import load_guide
    guides = {}
    for name in ["scheduling_preferences", "email_style"]:
        guides[name] = load_guide(name)

    metadata = {
        "thread_ids": [c.thread_id for c in EVAL_CASES] + (args.thread_ids or []),
        "lookback_days": lookback_days,
        "n_messages": len(messages),
        "n_events": len(events),
        "calendar_window": {"start": cal_start.isoformat(), "end": cal_end.isoformat()},
    }
    save_fixture(args.out, messages=messages, events=events, timezone=tz, guides=guides, metadata=metadata)
    print(f"Saved fixture to {args.out}", file=sys.stderr)


def _load_evals_file(filename: str) -> list[dict]:
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "evals", filename))
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def _load_canonical_classifier_evals() -> list[dict]:
    return _load_evals_file("classifier_canonical_evals.json")


def _load_canonical_draft_evals() -> list[dict]:
    return _load_evals_file("draft_canonical_evals.json")


def cmd_classify(args):
    """Run the classifier on specific messages from the fixture."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    results = run_classify_eval(fixture, thread_ids=args.thread_ids)

    print(json.dumps(results, indent=2))

    cases_with_expected = [r for r in results if "intent_match" in r]
    if cases_with_expected:
        passed = sum(1 for r in cases_with_expected if r["intent_match"])
        total = len(cases_with_expected)
        print(f"\n--- Classifier: {passed}/{total} intent matches ---", file=sys.stderr)
        for r in cases_with_expected:
            status = "PASS" if r["intent_match"] else "FAIL"
            print(f"  {status}  {r['description']:40s}  got={r['intent']:25s}  expected={r['expected_intent']}", file=sys.stderr)


def cmd_draft(args):
    """Run the draft composer against specific messages from the fixture."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    results = run_draft_eval(fixture, thread_ids=args.thread_ids)

    # Run LLM judge unless --no-judge
    if not args.no_judge:
        from scheduler.eval.judge import judge_draft_evals
        verdicts = judge_draft_evals(results)
        verdict_by_id = {v["eval_id"]: v for v in verdicts if "eval_id" in v}
        for r in results:
            if r.get("eval_id") in verdict_by_id:
                r["judge"] = verdict_by_id[r["eval_id"]]

    print(json.dumps(results, indent=2))

    cases_with_golden = [r for r in results if "golden_response" in r]
    if cases_with_golden:
        print(f"\n--- Draft eval summary ({len(cases_with_golden)} cases) ---", file=sys.stderr)
        for r in cases_with_golden:
            eval_id = r["eval_id"]
            judge = r.get("judge", {})
            if "verdict" in judge:
                verdict = judge["verdict"]
                score = judge.get("score", "?")
                max_score = judge.get("max_score", 5)
                summary = judge.get("summary", "")
                status = f"{'PASS' if verdict == 'PASS' else 'FAIL'}  {score}/{max_score}"
                print(f"\n  {status}  {eval_id}", file=sys.stderr)
                # Show which criteria failed
                for cname, cval in judge.get("criteria", {}).items():
                    if not cval.get("pass", False):
                        print(f"         FAIL {cname}: {cval.get('reason', '')}", file=sys.stderr)
                if summary:
                    print(f"         {summary}", file=sys.stderr)
            else:
                draft_body = (r.get("draft") or {}).get("body", "(no draft)")
                golden_body = r["golden_response"].get("body", "")
                print(f"\n  {eval_id}:", file=sys.stderr)
                print(f"    Golden:  {golden_body[:120]}", file=sys.stderr)
                print(f"    Got:     {draft_body[:120]}", file=sys.stderr)

        # Overall judge summary
        judged = [r for r in cases_with_golden if "judge" in r]
        if judged:
            passed = sum(1 for r in judged if r["judge"].get("verdict") == "PASS")
            total_score = sum(r["judge"].get("score", 0) for r in judged)
            max_total = sum(r["judge"].get("max_score", 5) for r in judged)
            print(f"\n--- Judge: {passed}/{len(judged)} PASS, {total_score}/{max_total} criteria passed ---", file=sys.stderr)


def cmd_reasoning(args):
    """Run reasoning email eval against specific messages from the fixture."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    results = run_reasoning_eval(fixture, thread_ids=args.thread_ids)

    if not args.no_judge:
        from scheduler.eval.judge import judge_reasoning_evals
        verdicts = judge_reasoning_evals(results)
        verdict_by_id = {v["eval_id"]: v for v in verdicts if "eval_id" in v}
        for r in results:
            if r.get("eval_id") in verdict_by_id:
                r["judge"] = verdict_by_id[r["eval_id"]]

    print(json.dumps(results, indent=2))

    produced = [r for r in results if r.get("reasoning_body")]
    print(f"\n--- Reasoning eval summary ({len(produced)} cases) ---", file=sys.stderr)
    for r in produced:
        eval_id = r["eval_id"]
        judge = r.get("judge", {})
        if "verdict" in judge:
            verdict = judge["verdict"]
            score = judge.get("score", "?")
            max_score = judge.get("max_score", 4)
            status = f"{'PASS' if verdict == 'PASS' else 'FAIL'}  {score}/{max_score}"
            print(f"\n  {status}  {eval_id}", file=sys.stderr)
            for cname, cval in judge.get("criteria", {}).items():
                if not cval.get("pass", False):
                    print(f"         FAIL {cname}: {cval.get('reason', '')}", file=sys.stderr)
            if judge.get("summary"):
                print(f"         {judge['summary']}", file=sys.stderr)
        else:
            body_preview = r["reasoning_body"][:120]
            print(f"\n  {eval_id}:", file=sys.stderr)
            print(f"    Body: {body_preview}", file=sys.stderr)

    judged = [r for r in produced if "judge" in r]
    if judged:
        passed = sum(1 for r in judged if r["judge"].get("verdict") == "PASS")
        total_score = sum(r["judge"].get("score", 0) for r in judged)
        max_total = sum(r["judge"].get("max_score", 4) for r in judged)
        print(f"\n--- Reasoning judge: {passed}/{len(judged)} PASS, {total_score}/{max_total} criteria passed ---", file=sys.stderr)


def cmd_lifecycle(args):
    """Run lifecycle (welcome email + draft reply) eval against the fixture."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    n_runs = args.runs or 3
    results = run_lifecycle_eval(fixture, n_runs)

    if not args.no_judge:
        from scheduler.eval.judge import judge_lifecycle_evals
        verdicts = judge_lifecycle_evals(results)
        verdict_by_id = {v["eval_id"]: v for v in verdicts if "eval_id" in v}
        for r in results:
            if r.get("eval_id") in verdict_by_id:
                r["judge"] = verdict_by_id[r["eval_id"]]

    print(json.dumps(results, indent=2))

    print(f"\n--- Lifecycle eval summary ({len(results)} runs) ---", file=sys.stderr)
    for r in results:
        eval_id = r.get("eval_id", "")
        if "error" in r:
            print(f"\n  ERROR  {eval_id}: {r['error']}", file=sys.stderr)
            continue

        welcome = r.get("welcome_email", {})
        print(f"\n  {eval_id}:", file=sys.stderr)
        print(f"    Welcome subject: {welcome.get('subject', '(none)')}", file=sys.stderr)
        print(f"    Welcome body:    {welcome.get('body', '')[:100]}...", file=sys.stderr)

        draft = r.get("draft_reply")
        if draft:
            print(f"    Draft reply:     {draft[:100]}...", file=sys.stderr)

        judge = r.get("judge", {})
        if "verdict" in judge:
            verdict = judge["verdict"]
            score = judge.get("score", "?")
            max_score = judge.get("max_score", 4)
            print(f"    Judge: {verdict}  {score}/{max_score}", file=sys.stderr)
            for cname, cval in judge.get("criteria", {}).items():
                if not cval.get("pass", False):
                    print(f"      FAIL {cname}: {cval.get('reason', '')}", file=sys.stderr)
            if judge.get("summary"):
                print(f"      {judge['summary']}", file=sys.stderr)

    judged = [r for r in results if "judge" in r]
    if judged:
        passed = sum(1 for r in judged if r["judge"].get("verdict") == "PASS")
        total_score = sum(r["judge"].get("score", 0) for r in judged)
        max_total = sum(r["judge"].get("max_score", 4) for r in judged)
        print(f"\n--- Lifecycle judge: {passed}/{len(judged)} PASS, {total_score}/{max_total} criteria passed ---", file=sys.stderr)


def cmd_guides(args):
    """Run guide-writer agents against the fixture."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    guides = run_guides_eval(fixture)
    print(json.dumps(guides, indent=2))


def run_updater_eval(fixture: dict, synthetic_diffs: list[dict] | None = None) -> dict:
    """Run the guide updater agents against synthetic diffs or fixture-derived diffs.

    If synthetic_diffs is None, derives diffs from the fixture messages
    (looks for messages with both an 'original_body' and 'sent_body' key, which
    you can add manually to test specific scenarios).

    Returns a dict with proposed_changes for each guide.
    """
    import anyio
    from scheduler.eval.backends import ReplayGuideBackend
    from scheduler.guides.updater import (
        STYLE_MIN_DRAFTS,
        PREFERENCES_MIN_DRAFTS,
        apply_proposed_changes,
        run_style_updater_agent,
        run_preferences_updater_agent,
    )

    class EvalUpdaterBackend:
        """Replay backend for updater evals — no DB calls."""

        def __init__(self, fixture: dict, diffs: list[dict]):
            self._fixture = fixture
            self._diffs = diffs
            self._logs: dict[str, str] = {}

        def load_guide(self, name: str) -> str | None:
            return self._fixture.get("guides", {}).get(name)

        def get_edited_drafts(self) -> list[dict]:
            return self._diffs

        def apply_guide_changes(self, guide_name: str, content: str) -> None:
            pass  # captured separately in the result

        def set_agent_log(self, guide_name: str, log: str) -> None:
            self._logs[guide_name] = log

        def get_agent_log(self, guide_name: str) -> str:
            return self._logs.get(guide_name, "")

    diffs = synthetic_diffs or fixture.get("updater_diffs", [])

    backend = EvalUpdaterBackend(fixture, diffs)

    results: dict[str, dict] = {}

    for guide_name, agent_fn, threshold in [
        ("email_style", run_style_updater_agent, STYLE_MIN_DRAFTS),
        ("scheduling_preferences", run_preferences_updater_agent, PREFERENCES_MIN_DRAFTS),
    ]:
        if len(diffs) < threshold:
            results[guide_name] = {
                "skipped": True,
                "reason": f"only {len(diffs)} diffs (need {threshold})",
            }
            continue
        try:
            proposed = anyio.run(agent_fn, backend, diffs)
            current = backend.load_guide(guide_name) or ""
            updated, applied = apply_proposed_changes(guide_name, current, proposed, threshold)
            results[guide_name] = {
                "current_guide": current,
                "proposed_changes": proposed,
                "applied_changes": applied,
                "updated_guide": updated if applied else current,
                "agent_log": backend.get_agent_log(guide_name),
            }
        except Exception as e:
            results[guide_name] = {"error": str(e)}

    return results


def cmd_updater(args):
    """Run the guide updater agent against synthetic diffs in a fixture."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    results = run_updater_eval(fixture)

    print(json.dumps(results, indent=2))

    for guide_name, result in results.items():
        if result.get("skipped"):
            print(f"\n  {guide_name}: SKIPPED — {result['reason']}", file=sys.stderr)
        elif result.get("error"):
            print(f"\n  {guide_name}: ERROR — {result['error']}", file=sys.stderr)
        else:
            n_proposed = len(result.get("proposed_changes", []))
            n_applied = len(result.get("applied_changes", []))
            print(f"\n  {guide_name}: {n_applied}/{n_proposed} changes applied", file=sys.stderr)
            for change in result.get("applied_changes", []):
                print(
                    f"    APPLIED [{change['action']}] {change['section']}: "
                    f"{change['justification'][:80]}",
                    file=sys.stderr,
                )
            for change in result.get("proposed_changes", []):
                if not change.get("applied") and change.get("skip_reason"):
                    print(
                        f"    SKIPPED [{change['action']}] {change['section']}: "
                        f"{change.get('skip_reason', '')}",
                        file=sys.stderr,
                    )


def cmd_onboard(args):
    """Run the onboarding (calendar populator) agent against the fixture."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)
    lookback_days = args.lookback_days or 60
    events = run_onboard_eval(fixture, lookback_days)

    print(json.dumps(events, indent=2))
    print(f"\n--- Onboarding eval: {len(events)} events added ---", file=sys.stderr)
    for ev in events:
        print(f"  {ev['start'][:16]}  {ev['summary']}", file=sys.stderr)


def cmd_list(args):
    """List all threads in a fixture so you can pick eval thread IDs."""
    from scheduler.eval.backends import load_fixture

    fixture = load_fixture(args.fixture)

    threads: dict[str, list[dict]] = {}
    for msg in fixture["messages"]:
        threads.setdefault(msg["thread_id"], []).append(msg)

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Eval CLI for scheduler agents")
    sub = parser.add_subparsers(dest="command", required=True)

    # run (unified)
    run = sub.add_parser("run", help="Run all evals end-to-end: guides -> onboard -> classify -> draft + reasoning")
    run.add_argument("--fixture", required=True, help="Fixture file")
    run.add_argument("--out", default="evals/results/run.json", help="Output results JSON (default: evals/results/run.json)")
    run.add_argument("--lookback-days", type=int, help="Lookback window for onboarding (default: 60)")
    run.add_argument("--no-judge", action="store_true", help="Skip LLM judge on draft evals")
    run.add_argument("--lifecycle-runs", type=int, help="Number of lifecycle eval runs (default: 3)")
    run.set_defaults(func=cmd_run)

    # record
    rec = sub.add_parser("record", help="Dump inbox + calendar to a fixture (run once)")
    rec.add_argument("--out", required=True, help="Output fixture file path")
    rec.add_argument("--thread-ids", nargs="*", help="Extra thread IDs to include for draft eval")
    rec.set_defaults(func=cmd_record)

    # list
    lst = sub.add_parser("list", help="List all threads in a fixture")
    lst.add_argument("--fixture", required=True, help="Fixture file")
    lst.set_defaults(func=cmd_list)

    # classify
    cls = sub.add_parser("classify", help="Run classifier on thread(s) from a fixture")
    cls.add_argument("--fixture", required=True, help="Fixture file")
    cls.add_argument("--thread-ids", nargs="*", help="Thread IDs (default: canonical evals)")
    cls.set_defaults(func=cmd_classify)

    # draft
    dft = sub.add_parser("draft", help="Run draft composer on thread(s) from a fixture")
    dft.add_argument("--fixture", required=True, help="Fixture file")
    dft.add_argument("--thread-ids", nargs="*", help="Thread IDs (default: canonical evals)")
    dft.add_argument("--no-judge", action="store_true", help="Skip LLM judge on draft evals")
    dft.set_defaults(func=cmd_draft)

    # reasoning
    reas = sub.add_parser("reasoning", help="Run reasoning email eval on thread(s) from a fixture")
    reas.add_argument("--fixture", required=True, help="Fixture file")
    reas.add_argument("--thread-ids", nargs="*", help="Thread IDs (default: canonical draft evals)")
    reas.add_argument("--no-judge", action="store_true", help="Skip LLM judge on reasoning evals")
    reas.set_defaults(func=cmd_reasoning)

    # lifecycle
    lc = sub.add_parser("lifecycle", help="Run lifecycle (welcome + draft reply) eval")
    lc.add_argument("--fixture", required=True, help="Fixture file")
    lc.add_argument("--runs", type=int, help="Number of independent runs (default: 3)")
    lc.add_argument("--no-judge", action="store_true", help="Skip LLM judge on lifecycle evals")
    lc.set_defaults(func=cmd_lifecycle)

    # guides
    gd = sub.add_parser("guides", help="Run guide-writer agents against a fixture")
    gd.add_argument("--fixture", required=True, help="Fixture file")
    gd.set_defaults(func=cmd_guides)

    # onboard
    ob = sub.add_parser("onboard", help="Run onboarding (calendar populator) agent against a fixture")
    ob.add_argument("--fixture", required=True, help="Fixture file")
    ob.add_argument("--lookback-days", type=int, help="Lookback window in days (default: 60)")
    ob.set_defaults(func=cmd_onboard)

    # updater
    upd = sub.add_parser(
        "updater",
        help="Run guide updater agents against synthetic diffs in a fixture "
             "(fixture must have an 'updater_diffs' key or use --diffs-file)",
    )
    upd.add_argument("--fixture", required=True, help="Fixture file")
    upd.set_defaults(func=cmd_updater)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
