If you are about to ask the user to do something for you, think about whether you can do it yourself.

### 0. Autonomy Rules

- **Never ask the user to check logs.** Check them yourself — via Render MCP, ngrok inspector (`localhost:4040`), or by running the server with captured output.
- **Never ask permission to kill/restart local processes.** If you need to restart uvicorn, ngrok, or any dev server to make progress, just do it.
- **Never speculate about env vars, API keys, or config.** If you need to know whether something is set, check it yourself (e.g. `env | grep`, read `.env`, etc.). Do not guess or assume.

### 1. Check Render Deployment

The control plane runs on Render as `scheduler-control-plane` (service ID: `srv-d6s55t1j16oc73eih6i0`).

- Use `mcp__render__list_logs` to check for errors after deploying, etc

### 2. Check Neon Database

Neon project: `blue-pine-43043371`. It has multiple branches — **always pass the correct branch ID**:

- **Dev branch**: `br-cold-mouse-am8uwd1y` (endpoint: `ep-solitary-dawn`) — this is what `.env` DATABASE_URL points to
- **Prod branch**: `br-shy-violet-am1llf2x` (endpoint: `ep-wild-voice`)

When using `mcp__neon__run_sql`, always include `branchId`:
```
mcp__neon__run_sql(projectId="blue-pine-43043371", branchId="br-cold-mouse-am8uwd1y", sql="...")
```

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