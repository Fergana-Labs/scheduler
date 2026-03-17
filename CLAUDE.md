When making changes, always verify they work end-to-end. If you are about to ask the user to check something for you, think about whether you can do it yourself.

### 1. Check Render Deployment

The control plane runs on Render as `scheduler-control-plane` (service ID: `srv-d6s55t1j16oc73eih6i0`).

- Use `mcp__render__list_logs` to check for errors after deploying, etc

### 2. Check Neon Database

The database is Neon project `blue-pine-43043371` (database: `neondb`).

- Use `mcp__neon__run_sql` to run migrations and verify table state

### 3. Refresh Gmail Watcher

You can do this with
```bash
curl -s -X POST https://scheduler-control-plane.onrender.com/api/v1/gmail/watch/renew
```

Expected response: `{"renewed": 1, "failed": []}`. If it fails, check that `GMAIL_PUBSUB_TOPIC` and `DATABASE_URL` are set on Render.

### 4. Send a Test Email

To test the e2e flow, send a scheduling email from a different account to the user's Gmail. Then:

- Watch Render logs for `gmail_webhook:` entries
- Confirm the classifier runs, draft composer fires, and draft appears in Gmail
- For invite testing: send the draft and check logs for `classify_sent_message_confirms_invite` and `created invite event`

### 5. Past Conversation Context

Previous Claude coding sessions are stored as `.jsonl` files at:
```
~/.claude/projects/-Users-henrydowling-projects-scheduler/
```

Read these to understand prior decisions, debugging sessions, and context that isn't in git history.