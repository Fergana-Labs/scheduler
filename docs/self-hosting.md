# Self-Hosting Guide

This guide walks through setting up Scheduler on your own infrastructure.

## Prerequisites

- Python 3.11+
- PostgreSQL database 
- Google Cloud project with Gmail and Calendar APIs enabled
- Anthropic API key

## 1. Environment variables

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

### Required

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | From Google Cloud Console → Credentials |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console → Credentials |
| `ANTHROPIC_API_KEY` | From console.anthropic.com |
| `DATABASE_URL` | PostgreSQL connection string |
| `SESSION_SECRET` | Random string for signing session tokens |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_DEPLOYMENT_MODE` | `self_hosted` | Auth mode (`self_hosted` or `auth0`) |
| `GMAIL_PUBSUB_TOPIC` | | Pub/Sub topic for Gmail push notifications |
| `GMAIL_WEBHOOK_TOKEN` | | Shared secret for webhook verification |
| `WEB_APP_URL` | `http://localhost:3000` | Frontend URL for CORS/redirects |
| `STASH_CALENDAR_NAME` | `Scheduled Calendar` | Name of the Google Calendar to create |
| `ONBOARDING_LOOKBACK_DAYS` | `60` | How far back onboarding scans Gmail |
| `WATCHER_POLL_INTERVAL` | `60` | Email watcher polling interval (seconds) |
| `AGENT_RUNTIME` | `local` | `local` or `e2b` (cloud sandbox) |

## 2. Google Cloud setup

### Create OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Gmail API** and **Google Calendar API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Add authorized redirect URIs:
   - `http://localhost:8080` (for local dev)
   - Your production control plane URL (if deploying)
7. Copy the Client ID and Client Secret to your `.env`

### Set up Gmail push notifications (optional but recommended)

Without Pub/Sub, the watcher polls Gmail on an interval. With Pub/Sub, you get real-time push notifications.

1. Enable the **Cloud Pub/Sub API** in your Google Cloud project
2. Create a Pub/Sub topic (e.g., `projects/your-project/topics/gmail-push`)
3. Grant `gmail-api-push@system.gserviceaccount.com` the **Pub/Sub Publisher** role on the topic
4. Create a push subscription pointing to your control plane:
   ```
   https://your-host/webhooks/gmail?token=YOUR_WEBHOOK_TOKEN
   ```
5. Set in `.env`:
   ```
   GMAIL_PUBSUB_TOPIC=projects/your-project/topics/gmail-push
   GMAIL_WEBHOOK_TOKEN=your-random-secret
   ```

## 3. Database setup

Run the SQL migrations in order:

```bash
psql $DATABASE_URL -f sql/000_create_users.sql
psql $DATABASE_URL -f sql/001_create_guides.sql
psql $DATABASE_URL -f sql/002_add_gmail_history_id.sql
psql $DATABASE_URL -f sql/003_add_stash_branding.sql
psql $DATABASE_URL -f sql/004_add_autopilot.sql
psql $DATABASE_URL -f sql/004_create_pending_invites.sql
psql $DATABASE_URL -f sql/005_add_google_meet.sql
psql $DATABASE_URL -f sql/006_add_system_enabled.sql
psql $DATABASE_URL -f sql/007_nullable_refresh_token.sql
psql $DATABASE_URL -f sql/008_add_sales_email_toggle.sql
psql $DATABASE_URL -f sql/009_create_processed_messages.sql
psql $DATABASE_URL -f sql/010_add_auth0_sub.sql
psql $DATABASE_URL -f sql/010_create_waitlist.sql
```

## 4. Authentication flow (self-hosted)

In `self_hosted` mode, Auth0 is not required. The flow is:

1. User visits your frontend and clicks "Connect Google"
2. Redirected to Google OAuth consent screen
3. After granting permissions, redirected back with an authorization code
4. Control plane exchanges the code for tokens, creates a user in the DB
5. User gets an HMAC-signed session token for subsequent API calls

To complete the initial OAuth flow locally:

```bash
python -m scheduler.auth.google_auth
```

This opens a browser window for Google OAuth and saves credentials to `token.json`.

## 5. Running the services

### Control plane (API server)

```bash
uvicorn scheduler.controlplane.server:app --host 0.0.0.0 --port 8080
```

### Email watcher

```bash
python -m scheduler.watcher
```

### Web frontend

```bash
cd web
npm install
NEXT_PUBLIC_CONTROL_PLANE_URL=http://localhost:8080 npm run dev
```

## 6. E2B sandbox mode (optional)

E2B lets you run agents in isolated cloud sandboxes instead of locally. This is useful for multi-tenant deployments where you don't want user agents sharing a process.

### Setup

1. Sign up at [e2b.dev](https://e2b.dev) and get an API key
2. Build a sandbox template:
   ```bash
   e2b template build -n scheduler-agents
   ```
3. Set in `.env`:
   ```
   AGENT_RUNTIME=e2b
   E2B_API_KEY=your-key
   E2B_TEMPLATE_ID=scheduler-agents
   CONTROL_PLANE_PUBLIC_URL=https://your-control-plane-url
   ```

When `AGENT_RUNTIME=local` (default), agents run in the same process as the control plane. No E2B account is needed.

## 7. Production deployment

The control plane is a standard FastAPI app. Deploy it anywhere you can run Python:

- **Render**: Add as a Web Service, set env vars in the dashboard
- **Railway**: Similar to Render
- **Docker**: `uvicorn scheduler.controlplane.server:app --host 0.0.0.0 --port 8080`
- **Fly.io**: Add a `fly.toml` with the uvicorn command

The frontend is a Next.js app that can be deployed to Vercel, Netlify, or any Node.js host. Set `NEXT_PUBLIC_CONTROL_PLANE_URL` to point at your control plane.
