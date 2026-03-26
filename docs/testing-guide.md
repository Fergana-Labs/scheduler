# Testing the Matrix Chat Integration

Three options for testing, from quickest to most complete.

---

## Option A: Pure Local (no bridges, no tunnel)

Tests the full code pipeline without real WhatsApp/Instagram. Good for verifying everything compiles, connects, and flows correctly.

### 1. Run Matrix stack locally

```bash
cd matrix
cp .env.example .env
```

Edit `.env`:
```
MATRIX_DOMAIN=localhost
POSTGRES_PASSWORD=testpassword
REGISTRATION_SHARED_SECRET=testsecret
BOT_PASSWORD=botpassword
```

```bash
bash setup.sh
```

### 2. Run DB migrations

```bash
psql $DATABASE_URL -f sql/015_add_matrix_credentials.sql
psql $DATABASE_URL -f sql/016_create_pending_replies.sql
```

### 3. Install dependency

```bash
pip install "matrix-nio>=0.24.0"
```

### 4. Configure Scheduled

Add to your `.env`:
```
MATRIX_HOMESERVER_URL=http://localhost:8008
MATRIX_ACCESS_TOKEN=<from setup.sh output>
MATRIX_USER_ID=@scheduler-bot:localhost
MATRIX_SYNC_ENABLED=true
```

### 5. Create a test user and send messages

```bash
# Create a second user to simulate incoming messages
docker exec -it synapse register_new_matrix_user \
    http://localhost:8008 -c /data/homeserver.yaml \
    -u testuser -p testpassword --no-admin

# Get their access token
curl -s -X POST http://localhost:8008/_matrix/client/v3/login \
    -H "Content-Type: application/json" \
    -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"testuser"},"password":"testpassword"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
```

Use the test user's token to create a room and send messages:

```bash
TOKEN=<testuser token>
BOT_TOKEN=<scheduler-bot token>

# Create a DM room and invite the bot
ROOM_ID=$(curl -s -X POST http://localhost:8008/_matrix/client/v3/createRoom \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"is_direct":true,"invite":["@scheduler-bot:localhost"]}' | python3 -c "import sys,json; print(json.load(sys.stdin)['room_id'])")

echo "Room ID: $ROOM_ID"

# Bot joins the room
curl -s -X POST "http://localhost:8008/_matrix/client/v3/rooms/$ROOM_ID/join" \
    -H "Authorization: Bearer $BOT_TOKEN" \
    -H "Content-Type: application/json" -d '{}'

# Send a scheduling message as the test user
curl -s -X POST "http://localhost:8008/_matrix/client/v3/rooms/$ROOM_ID/send/m.room.message" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"msgtype":"m.text","body":"Hey, want to grab coffee on Thursday?"}'
```

### 6. Start Scheduled and watch logs

```bash
uvicorn scheduler.controlplane.server:app --reload
```

Watch for:
- `matrix_watcher: starting for user=...`
- `matrix_watcher: processing 1 message(s) from testuser...`
- `classifier: messages classified as needs_draft`
- `chat_composer: created pending reply`

### 7. Check the results

```bash
# List pending replies via API
curl -s -H "Authorization: Bearer <your session token>" \
    http://localhost:8000/web/api/v1/chat/pending | python3 -m json.tool
```

Or open `http://localhost:3000/inbox` in the web UI.

### What this tests

- Matrix client connects to Synapse ✅
- Watcher receives messages via sync loop ✅
- Pre-filters work (emoji, short messages skipped) ✅
- Classifier identifies scheduling intent ✅
- Composer drafts a reply ✅
- Pending replies stored in DB ✅
- API endpoints return pending replies ✅
- Inbox UI displays drafts ✅
- Approve sends message back via Matrix ✅

### What this doesn't test

- Actual WhatsApp/Instagram/LinkedIn message delivery
- Bridge bot login flows (QR code, cookies)
- Platform-specific message formatting

---

## Option B: Local + ngrok (real bridges, real platforms)

Tests everything including actual WhatsApp/Instagram messages flowing through bridges.

### 1. Get a stable ngrok domain

1. Sign up at [ngrok.com](https://ngrok.com)
2. Go to **Domains** → claim your free static domain (e.g., `yourname.ngrok-free.app`)
3. Install ngrok: `brew install ngrok`
4. Auth: `ngrok config add-authtoken <your-token>`

**Important:** Matrix server names are permanent (`@user:yourname.ngrok-free.app`). Use a stable domain, not a random one.

### 2. Run Matrix stack

```bash
cd matrix
cp .env.example .env
```

Edit `.env`:
```
MATRIX_DOMAIN=yourname.ngrok-free.app
POSTGRES_PASSWORD=<generate: openssl rand -hex 16>
REGISTRATION_SHARED_SECRET=<generate: openssl rand -hex 32>
BOT_PASSWORD=<generate: openssl rand -hex 16>
```

```bash
bash setup.sh
```

### 3. Start ngrok tunnel

```bash
ngrok http 8008 --domain=yourname.ngrok-free.app
```

Keep this running in a separate terminal.

### 4. Verify Synapse is reachable

```bash
curl https://yourname.ngrok-free.app/health
# Expected: OK
```

### 5. Run DB migrations + install dependency

```bash
psql $DATABASE_URL -f sql/015_add_matrix_credentials.sql
psql $DATABASE_URL -f sql/016_create_pending_replies.sql
pip install "matrix-nio>=0.24.0"
```

### 6. Configure Scheduled

Add to your `.env`:
```
MATRIX_HOMESERVER_URL=https://yourname.ngrok-free.app
MATRIX_ACCESS_TOKEN=<from setup.sh output>
MATRIX_USER_ID=@scheduler-bot:yourname.ngrok-free.app
MATRIX_SYNC_ENABLED=true
```

### 7. Link WhatsApp

Start Scheduled:
```bash
uvicorn scheduler.controlplane.server:app --reload
```

Then either:
- Open `/connections` in the web UI and click "Connect" on WhatsApp
- Or manually via curl:

```bash
# Start login flow
curl -s -X POST http://localhost:8000/web/api/v1/bridges/whatsapp/login \
    -H "Authorization: Bearer <session token>" \
    -H "Content-Type: application/json" | python3 -m json.tool

# The response includes a QR code image URL — open it in a browser and scan with WhatsApp
```

### 8. Test end-to-end

1. Have someone send you a WhatsApp message: "Hey, are you free for lunch Friday?"
2. Watch Scheduled logs for the watcher → classifier → composer pipeline
3. Open `/inbox` — pending reply should appear
4. Click "Send" — reply goes back through WhatsApp

### What this tests additionally

- Bridge bot login flows (QR code display, cookie auth) ✅
- Real WhatsApp/Instagram/LinkedIn message delivery ✅
- Media handling through bridges ✅
- Connection status detection ✅

---

## Option C: Production (Hetzner server)

For when you're ready to run this permanently.

### 1. Provision server

- [Hetzner Cloud Console](https://console.hetzner.cloud)
- Create project → Add server
- Image: **Ubuntu 24.04**
- Type: **CX22** (2 vCPU, 4GB RAM, 40GB disk, ~$4.50/mo)
- Add your SSH key
- Create

### 2. Point DNS

Add an A record: `matrix.yourdomain.com` → `<server IP>`

Wait for DNS propagation (check with `dig matrix.yourdomain.com`).

### 3. Set up the server

```bash
ssh root@<server-ip>

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone repo
git clone <your-repo-url> scheduler
cd scheduler/matrix

# Configure
cp .env.example .env
nano .env  # Set MATRIX_DOMAIN, passwords

# Run setup
bash setup.sh
```

### 4. Configure Scheduled

Add the credentials from setup.sh output to your Render deployment (or local `.env`):
```
MATRIX_HOMESERVER_URL=https://matrix.yourdomain.com
MATRIX_ACCESS_TOKEN=<from setup.sh>
MATRIX_USER_ID=@scheduler-bot:matrix.yourdomain.com
MATRIX_SYNC_ENABLED=true
```

### 5. Run DB migrations

```bash
psql $DATABASE_URL -f sql/015_add_matrix_credentials.sql
psql $DATABASE_URL -f sql/016_create_pending_replies.sql
```

### 6. Link platforms and test

Same as Option B steps 7-8, but using your production domain.

---

## Quick smoke tests (no server needed)

These test individual components without any Matrix infrastructure.

### Test the classifier

```bash
PYTHONPATH=src python -c "
from scheduler.classifier.intent import classify_chat_message
r = classify_chat_message('Hey want to grab coffee Thursday?', 'John', 'whatsapp')
print(f'Intent: {r.intent.value}')
print(f'Confidence: {r.confidence}')
print(f'Summary: {r.summary}')
"
```

### Test pre-filters

```bash
PYTHONPATH=src python -c "
from scheduler.matrix.watcher import _passes_prefilter, _is_emoji_only
from scheduler.matrix.models import ChatMessage
from datetime import datetime

msg = ChatMessage('e1', 'r1', '@other:localhost', 'Other', 'Hey!', datetime.now(), 'whatsapp')
print(f'\"Hey!\" passes: {_passes_prefilter(msg, \"@me:localhost\")}')  # False (< 5 chars)

msg2 = ChatMessage('e2', 'r1', '@other:localhost', 'Other', 'Want to get lunch tomorrow?', datetime.now(), 'whatsapp')
print(f'\"Want to get lunch tomorrow?\" passes: {_passes_prefilter(msg2, \"@me:localhost\")}')  # True

print(f'Emoji only \"😀🎉\": {_is_emoji_only(\"😀🎉\")}')  # True
print(f'Not emoji \"hello 😀\": {_is_emoji_only(\"hello 😀\")}')  # False
"
```

### Test pending replies DB

```bash
PYTHONPATH=src python -c "
from scheduler.db import create_pending_reply, get_pending_replies, approve_pending_reply

# Create
r = create_pending_reply(
    user_id='<your user id>',
    platform='whatsapp',
    room_id='!test:localhost',
    sender_name='John',
    proposed_reply='How about Thursday at 2pm?',
    conversation_context=[{'sender': 'John', 'body': 'Want to grab coffee?'}]
)
print(f'Created: {r.id}')

# List
replies = get_pending_replies('<your user id>')
print(f'Pending: {len(replies)}')

# Approve
approved = approve_pending_reply(str(r.id))
print(f'Approved: {approved.status}')
"
```

### Test frontend pages

```bash
cd web
npm run dev
```

- `http://localhost:3000/inbox` — empty state with "No pending replies"
- `http://localhost:3000/connections` — platform cards (will show "Matrix not configured" warning without backend)
