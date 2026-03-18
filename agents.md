If you are about to ask the user to do something for you, think about whether you can do it yourself.

### 0. Autonomy Rules

- **Never ask the user to check logs.** Check them yourself — via Render MCP, ngrok inspector (`localhost:4040`), or by running the server with captured output.
- **Never ask permission to kill/restart local processes.** If you need to restart uvicorn, ngrok, or any dev server to make progress, just do it.
- **Never speculate about env vars, API keys, or config.** If you need to know whether something is set, check it yourself (e.g. `env | grep`, read `.env`, etc.). Do not guess or assume. Do not ask the user. Check it yourself.

### 1. Check Render Deployment

The control plane runs on Render as `scheduler-control-plane` (service ID: `srv-d6s55t1j16oc73eih6i0`).

- Use `mcp__render__list_logs` to check for errors after deploying, etc

Do not ask the user to check render. Check it yourself.

### 2. Check Neon Database

Neon project: `blue-pine-43043371`. It has multiple branches — **always pass the correct branch ID**:

- **Dev branch**: `br-cold-mouse-am8uwd1y` (endpoint: `ep-solitary-dawn`) — this is what `.env` DATABASE_URL points to
- **Prod branch**: `br-shy-violet-am1llf2x` (endpoint: `ep-wild-voice`)

When using `mcp__neon__run_sql`, always include `branchId`:
```
mcp__neon__run_sql(projectId="blue-pine-43043371", branchId="br-cold-mouse-am8uwd1y", sql="...")
```

Do not ask the user to check neon. Check it yourself.

### 3. Refresh Gmail Watcher

You can do this with
```bash
curl -s -X POST https://scheduler-control-plane.onrender.com/api/v1/gmail/watch/renew
```

Expected response: `{"renewed": 1, "failed": []}`. If it fails, check that `GMAIL_PUBSUB_TOPIC` and `DATABASE_URL` are set on Render.

### 4. Send a Test Email

To test the e2e flow, send a scheduling email from a second Gmail account to henry@ferganalabs.com.

**Step 1: Get test sender credentials** (one-time, or if `/tmp/test_sender_token.json` is missing/expired)

```bash
lsof -ti:8080 | xargs kill 2>/dev/null; sleep 1

python3 -c "
import sys; sys.path.insert(0, 'src')
from scheduler.config import config
from google_auth_oauthlib.flow import InstalledAppFlow

client_config = {
    'installed': {
        'client_id': config.google_client_id,
        'client_secret': config.google_client_secret,
        'redirect_uris': ['http://localhost:8080'],
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
    }
}

flow = InstalledAppFlow.from_client_config(client_config, ['https://www.googleapis.com/auth/gmail.send'])
creds = flow.run_local_server(port=8080, redirect_uri_trailing_slash=False)

with open('/tmp/test_sender_token.json', 'w') as f:
    f.write(creds.to_json())
print('OAuth complete! Token saved.')
"
```

The user will need to log in with a **different** Google account (not henry@ferganalabs.com) in the browser popup.

**Step 2: Send test email**

```bash
python3 -c "
import json, base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

with open('/tmp/test_sender_token.json') as f:
    creds = Credentials.from_authorized_user_info(json.load(f))

service = build('gmail', 'v1', credentials=creds)

msg = MIMEText('Hey, are you free for a call on Thursday? Would love to catch up!')
msg['to'] = 'henry@ferganalabs.com'
msg['subject'] = 'Call Thursday?'

raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
print(f'Sent message ID: {result[\"id\"]}')
"
```

**Step 3: Verify**

- Watch Render logs for `gmail_webhook:` entries
- Confirm the classifier runs, draft composer fires, and draft appears in Gmail
- For invite testing: send the draft and check logs for `classify_sent_message_confirms_invite` and `created invite event`

Do not ask the user to send an email. Do it yourself.

### 5. Past Conversation Context

Previous Claude coding sessions are stored as `.jsonl` files at:
```
~/.claude/projects/-Users-henrydowling-projects-scheduler/
```

Read these to understand prior decisions, debugging sessions, and context that isn't in git history.

### 6. Testing a UI with playwright

You have access to the Playwright MCP. Use it to verify any UI changes that you make for the user. Do not ask the user
to check to see if your UI changes worked or not. Use the Playwright MCP, and do it yourself.