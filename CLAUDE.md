# Scheduler

## Project structure

```
src/scheduler/
├── auth/google_auth.py    — Google OAuth2 flow (Gmail + Calendar scopes)
├── gmail/client.py        — Gmail API: read emails, create drafts
├── calendar/client.py     — Google Calendar API: stash calendar CRUD
├── classifier/intent.py   — LLM classifier: is this email about scheduling?
├── availability/checker.py — Find open time slots across all calendars
├── drafts/composer.py     — Compose draft replies with proposed times
├── onboarding.py          — Backfill stash calendar from Gmail history
├── hook.py                — Process new messages, update stash calendar
├── watcher.py             — Main loop: poll Gmail, classify, draft
└── config.py              — Environment config
```

## Commands

- `pip install -e ".[dev]"` — install with dev deps
- `pytest` — run tests
- `ruff check src/` — lint
- `python -m scheduler.watcher` — run the email watcher
- `python -m scheduler.onboarding` — run onboarding backfill

## Key decisions

- **Stash calendar approach**: A real Google Calendar is the single source of truth for all commitments. This lets users see it too.
- **v0 scope**: Google Calendar only. Text messages (v1) and Beeper/Slack (v2) come later.
- Uses Claude (via Anthropic API) for email classification and draft composition.
- Google OAuth uses same scopes/approach as Fyxer for creating drafts.
