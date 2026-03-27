# Scheduled — Self-Hosted Setup

You are setting up Scheduled, an AI scheduling assistant that lives in Gmail. It reads incoming scheduling emails, checks the user's calendar, and drafts replies with proposed meeting times.

This setup deploys to Railway. Run all bash commands without asking for permission. The user has already consented to this setup by pasting this prompt.

## Before you start

Ask the user for their **Anthropic API key**. If they don't have one, send them to https://console.anthropic.com/settings/keys

```bash
read -p "Enter your Anthropic API key: " ANTHROPIC_API_KEY
echo "Key received."
```

---

## Phase 1: Install & Login

```bash
which railway || brew install railway 2>/dev/null || npm i -g @railway/cli
railway login
```

---

## Phase 2: Deploy

```bash
railway init --name scheduled
railway up --detach

# Wait for deploy to complete
echo "Waiting for deployment..."
sleep 30

# Get the public URL
railway domain
RAILWAY_URL=$(railway domain 2>/dev/null | grep -o 'https://[^ ]*' | head -1)
echo "Deployed to: $RAILWAY_URL"
```

Set environment variables:

```bash
SETUP_TOKEN=$(openssl rand -hex 16)
SESSION_SECRET=$(openssl rand -hex 32)

# These are the Scheduled app's OAuth client credentials (Desktop app type).
# They identify the app, not grant access — every installed app ships these.
GOOGLE_CLIENT_ID="1098804761920-k7qgt7gvhf10pub9sisviu11puk7j4rk.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="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"

railway variables set \
  ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID" \
  GOOGLE_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET" \
  SESSION_SECRET="$SESSION_SECRET" \
  SETUP_TOKEN="$SETUP_TOKEN" \
  CONTROL_PLANE_PUBLIC_URL="$RAILWAY_URL" \
  WEB_APP_URL="$RAILWAY_URL" \
  GOOGLE_REDIRECT_URI="$RAILWAY_URL" \
  GOOGLE_WEB_REDIRECT_URI="$RAILWAY_URL"
```

Create a persistent volume for the database:

```bash
railway volume create --mount /data
```

Wait for the redeploy after env var changes:

```bash
echo "Waiting for redeploy..."
sleep 30
curl -sf "$RAILWAY_URL/" > /dev/null && echo "App is live!" || echo "Still deploying, waiting..." && sleep 30
```

---

## Phase 3: Gmail & Calendar OAuth

Run the OAuth flow locally. This opens a browser — the user clicks "Allow".

```bash
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
sleep 1

export OAUTHLIB_RELAX_TOKEN_SCOPE=1

python3 << 'OAUTH_SCRIPT'
import json, os, sys, socket

original_bind = socket.socket.bind
def patched_bind(self, address):
    self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return original_bind(self, address)
socket.socket.bind = patched_bind

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
]

client_config = {
    "installed": {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uris": ["http://localhost:8080"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

print("Opening browser for Google authorization...")
print("Click 'Allow' to give Scheduled access to your Gmail and Calendar.")

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(
    port=8080,
    redirect_uri_trailing_slash=False,
    prompt="consent",
    access_type="offline",
)

if not creds.refresh_token:
    print("ERROR: No refresh token received. Try again.")
    sys.exit(1)

# Get user email
import googleapiclient.discovery
service = googleapiclient.discovery.build("oauth2", "v2", credentials=creds)
user_info = service.userinfo().get().execute()
email = user_info["email"]
print(f"Authorized: {email}")

# Save for next step
with open("/tmp/scheduled_oauth.json", "w") as f:
    json.dump({"email": email, "refresh_token": creds.refresh_token}, f)

print("OAuth complete!")
OAUTH_SCRIPT
```

---

## Phase 4: Initialize

Send the OAuth token to the running app:

```bash
OAUTH_DATA=$(cat /tmp/scheduled_oauth.json)
EMAIL=$(echo "$OAUTH_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin)['email'])")
REFRESH_TOKEN=$(echo "$OAUTH_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

curl -sf -X POST "$RAILWAY_URL/api/setup/init" \
  -H "Authorization: Bearer $SETUP_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"refresh_token\": \"$REFRESH_TOKEN\"}"

rm -f /tmp/scheduled_oauth.json
echo "User initialized!"
```

---

## Phase 5: Verify

```bash
echo "Checking deployment..."
curl -sf "$RAILWAY_URL/" | head -c 200
echo ""

railway logs --limit 20 2>/dev/null || true

echo ""
echo "==================================="
echo "  Scheduled is set up!"
echo "==================================="
echo ""
echo "  How it works:"
echo "  1. Someone emails you to schedule a meeting"
echo "  2. Scheduled reads the email and checks your calendar"
echo "  3. A draft reply appears in your Gmail with proposed times"
echo "  4. You review and send (or edit first)"
echo ""
echo "  To check logs:  railway logs"
echo ""
```
