# Scheduler

Inbound scheduling agent — automatically drafts email responses with proposed meeting times by checking all the places you store your commitments. Saves us a ton of time on recruiting, we hope it saves you time as well!

## Self-Hosted Setup

See [docs/self-hosting.md](docs/self-hosting.md) for detailed instructions including GCP webhook setup and optional E2B sandboxing. If you are considering self hosting, feel free to reach out to henry@ferganalabs.com or sam@ferganalabs.com and we can help you get set up.

### Quick start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Fill in: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ANTHROPIC_API_KEY, DATABASE_URL
# SCHEDULER_DEPLOYMENT_MODE defaults to self_hosted (no Auth0 needed)

# Authenticate with Google
python -m scheduler.auth.google_auth

# Run onboarding (backfill scheduled calendar from last 2 months of Gmail)
python -m scheduler.onboarding

# Start the email watcher (monitors for scheduling emails, creates drafts)
python -m scheduler.watcher
```

## Run the app

```bash
# Control plane (API)
uvicorn scheduler.controlplane.server:app --host 0.0.0.0 --port 8080

# Frontend (separate terminal)
cd web && NEXT_PUBLIC_CONTROL_PLANE_URL=http://localhost:8080 npm run dev
```

## Running locally versus our production setup

The app can run with plain Google OAuth without any user authentication (this is how we originally ran it locally). We use Auth0 for auth in production since it supports multi-tenant.

We also run our agents in e2b sandboxes rather than locally. You can also run your agents on e2b if you want:

```bash
# Build a preprovisioned sandbox template
e2b template build -n scheduler-agents

# Configure
export AGENT_RUNTIME=e2b
export CONTROL_PLANE_PUBLIC_URL=https://your-control-plane-url
export E2B_TEMPLATE_ID=scheduler-agents
```

If `E2B_TEMPLATE_ID` is unset, the code falls back to runtime provisioning inside a fresh sandbox.

## License

MIT

## Demo Video
TODO