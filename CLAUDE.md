# Scheduler

## Project structure

```
src/scheduler/
├── auth/google_auth.py           — Google OAuth2 flow (Gmail + Calendar scopes)
├── gmail/client.py               — Gmail API: read emails, create drafts
├── calendar/client.py            — Google Calendar API: stash calendar CRUD
├── classifier/intent.py          — LLM classifier: is this email about scheduling?
├── drafts/composer.py            — Agent: reads calendar, composes draft replies with proposed times
├── onboarding.py                 — Backfill stash calendar from Gmail history (local mode)
├── controlplane/server.py        — FastAPI control plane: exposes Gmail/Calendar as HTTP endpoints, holds auth tokens
├── sandbox/onboarding.py         — Sandbox onboarding agent: calls control plane over HTTP, no tokens
├── sandbox/api_client.py         — HTTP client for control plane endpoints
├── run_e2b.py                    — Orchestrator: starts control plane, spins up e2b sandbox, runs agent
├── hook.py                       — Process new messages, update stash calendar
├── watcher.py                    — Main loop: poll Gmail, classify, draft
└── config.py                     — Environment config
```

## Commands

- `pip install -e ".[dev]"` — install with dev deps
- `pytest` — run tests
- `ruff check src/` — lint
- `python -m scheduler.watcher` — run the email watcher
- `python -m scheduler.onboarding` — run onboarding backfill (local)
- `python -m scheduler.run_e2b` — run onboarding in e2b sandbox via control plane
- `python -m scheduler.run_e2b <control_plane_url>` — same, with a deployed control plane

## Key decisions

- **Stash calendar approach**: A real Google Calendar is the single source of truth for all commitments. This lets users see it too.
- **v0 scope**: Google Calendar only. Text messages (v1) and Beeper/Slack (v2) come later.
- Google OAuth uses same scopes/approach as Fyxer for creating drafts.

### LLM completion vs agent

Two agents, one LLM completion:

| Component | Type | Why |
|---|---|---|
| `classifier/intent.py` | **LLM completion** | Simple classification — single API call with structured output, no tools needed |
| `drafts/composer.py` | **Agent** | Reads the calendar directly, reasons about real availability (buffers, meal times, etc.), composes the draft |
| `onboarding.py` | **Agent** | Needs to iteratively search Gmail with different queries, read threads, cross-reference calendar, decide when done |
