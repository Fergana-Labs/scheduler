# Self-Hosting Matrix Synapse with mautrix Bridges

A step-by-step guide to running Matrix Synapse with mautrix bridges for WhatsApp, Instagram, and LinkedIn. This gives Scheduler a unified Matrix-based message bus for all three chat platforms.

**Prerequisites**: Docker, Docker Compose v2, a Linux server (or Mac for local dev), and a domain name with DNS pointing at your server.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Synapse Deployment](#2-synapse-deployment)
3. [Getting an Access Token](#3-getting-an-access-token)
4. [mautrix-whatsapp Bridge](#4-mautrix-whatsapp-bridge)
5. [mautrix-meta Bridge (Instagram)](#5-mautrix-meta-bridge-instagram)
6. [mautrix-linkedin Bridge](#6-mautrix-linkedin-bridge)
7. [Complete Docker Compose File](#7-complete-docker-compose-file)
8. [Common Gotchas](#8-common-gotchas)
9. [Verifying It Works](#9-verifying-it-works)

---

## 1. Architecture Overview

```
WhatsApp  ──>  mautrix-whatsapp  ──┐
Instagram ──>  mautrix-meta      ──┼──>  Synapse  ──>  Your App
LinkedIn  ──>  mautrix-linkedin  ──┘        │
                                        PostgreSQL
```

Each bridge runs as an **appservice** -- a sidecar process that registers with Synapse via a `registration.yaml` file. Synapse pushes events to the bridge over HTTP; the bridge pushes events back. All messages end up in Matrix rooms that your app can read via the Matrix Client-Server API.

**Ports used in this guide:**

| Service            | Internal Port | Purpose                          |
|--------------------|---------------|----------------------------------|
| Synapse            | 8008          | Client-Server + Federation API   |
| PostgreSQL         | 5432          | Database                         |
| mautrix-whatsapp   | 29318         | Appservice HTTP listener         |
| mautrix-meta       | 29319         | Appservice HTTP listener         |
| mautrix-linkedin   | 29320         | Appservice HTTP listener         |
| Caddy              | 80, 443       | Reverse proxy + TLS              |

---

## 2. Synapse Deployment

### 2.1 Directory Structure

Create a working directory:

```bash
mkdir -p matrix-server/{synapse,postgres,bridges/{whatsapp,meta,linkedin}}
cd matrix-server
```

### 2.2 Generate Synapse Config

Run the Synapse container once in `generate` mode to create `homeserver.yaml`:

```bash
docker run -it --rm \
    -v $(pwd)/synapse:/data \
    -e SYNAPSE_SERVER_NAME=matrix.example.com \
    -e SYNAPSE_REPORT_STATS=no \
    matrixdotorg/synapse:latest generate
```

This creates `/data/homeserver.yaml` (mapped to `./synapse/homeserver.yaml` on your host) plus a signing key and log config.

Replace `matrix.example.com` with your actual domain. This value is permanent -- it becomes part of every user ID (`@user:matrix.example.com`) and cannot be changed later.

### 2.3 Configure PostgreSQL

Edit `synapse/homeserver.yaml`. Find the `database` section (it defaults to SQLite) and replace it:

```yaml
database:
  name: psycopg2
  args:
    user: synapse
    password: change-me-to-a-strong-password
    database: synapse
    host: postgres
    port: 5432
    cp_min: 5
    cp_max: 10
```

The `host: postgres` refers to the Docker Compose service name (not localhost).

### 2.4 Configure the HTTP Listener

In the same `homeserver.yaml`, find the `listeners` section and make sure it looks like this:

```yaml
listeners:
  - port: 8008
    tls: false
    type: http
    x_forwarded: true
    resources:
      - names: [client, federation]
        compress: false
```

Key points:
- `x_forwarded: true` is required when running behind a reverse proxy (Caddy/nginx) so Synapse reads the real client IP from the `X-Forwarded-For` header.
- Do NOT set `bind_addresses: ['127.0.0.1']` inside Docker -- the reverse proxy needs to reach the container on its Docker network interface.

### 2.5 Appservice Registration (placeholder)

Add this to `homeserver.yaml` -- you will create these files in the bridge setup steps below:

```yaml
app_service_config_files:
  - /data/whatsapp-registration.yaml
  - /data/meta-registration.yaml
  - /data/linkedin-registration.yaml
```

### 2.6 Other Recommended Settings

```yaml
# Disable open registration (you'll create users manually)
enable_registration: false

# Required for register_new_matrix_user CLI tool
registration_shared_secret: "generate-a-long-random-string-here"

# Suppress nag if you don't want to report stats
report_stats: false

# Increase upload limit for media from bridges
max_upload_size: 50M
```

Generate a strong random string for `registration_shared_secret`:

```bash
openssl rand -hex 32
```

### 2.7 Reverse Proxy with Caddy

Caddy handles TLS automatically via Let's Encrypt. Create a `Caddyfile`:

```
matrix.example.com {
    reverse_proxy /_matrix/* synapse:8008
    reverse_proxy /_synapse/client/* synapse:8008
}
```

If your domain is the same as the server name, you also need `.well-known` delegation. If Matrix lives on a subdomain, serve these from the parent domain:

```
example.com {
    header /.well-known/matrix/* Content-Type application/json
    header /.well-known/matrix/* Access-Control-Allow-Origin *
    respond /.well-known/matrix/server `{"m.server": "matrix.example.com:443"}`
    respond /.well-known/matrix/client `{"m.homeserver":{"base_url":"https://matrix.example.com"}}`
}
```

**Alternative: nginx** -- if you prefer nginx, the key config is:

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name matrix.example.com;

    # TLS certs (e.g. from certbot)
    ssl_certificate /etc/letsencrypt/live/matrix.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/matrix.example.com/privkey.pem;

    location ~ ^(/_matrix|/_synapse/client) {
        proxy_pass http://synapse:8008;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        client_max_body_size 50M;
        proxy_http_version 1.1;
    }
}
```

---

## 3. Getting an Access Token

Your app needs a Matrix access token to interact with rooms programmatically.

### 3.1 Create an Admin User

With Synapse running, exec into the container:

```bash
docker exec -it synapse register_new_matrix_user \
    http://localhost:8008 \
    -c /data/homeserver.yaml \
    -u scheduler-bot \
    -p 'a-strong-password' \
    -a
```

The `-a` flag makes the user a server admin. The `-c` flag points to the config file so the tool can read the `registration_shared_secret`.

### 3.2 Get an Access Token via the Login API

```bash
curl -s -X POST https://matrix.example.com/_matrix/client/v3/login \
    -H "Content-Type: application/json" \
    -d '{
        "type": "m.login.password",
        "identifier": {
            "type": "m.id.user",
            "user": "scheduler-bot"
        },
        "password": "a-strong-password"
    }' | jq .
```

Response:

```json
{
    "user_id": "@scheduler-bot:matrix.example.com",
    "access_token": "syt_c2NoZWR1bGVyLWJvdA_ABCDEfghij_1a2b3c",
    "device_id": "ABCDEFGHIJ",
    "home_server": "matrix.example.com"
}
```

Save the `access_token` value. This is what your app uses in the `Authorization: Bearer <token>` header for all Matrix API calls.

**For local dev** (before Caddy is set up), you can call Synapse directly at `http://localhost:8008` instead of the HTTPS URL.

### 3.3 Verify the Token Works

```bash
curl -s -H "Authorization: Bearer syt_c2NoZWR1bGVyLWJvdA_ABCDEfghij_1a2b3c" \
    https://matrix.example.com/_matrix/client/v3/account/whoami | jq .
```

Expected:
```json
{
    "user_id": "@scheduler-bot:matrix.example.com"
}
```

---

## 4. mautrix-whatsapp Bridge

### 4.1 Generate Config

```bash
cd bridges/whatsapp
docker run --rm -v $(pwd):/data:z dock.mau.dev/mautrix/whatsapp:latest
```

This creates `config.yaml` in `./bridges/whatsapp/`.

### 4.2 Edit config.yaml

Open `bridges/whatsapp/config.yaml` and change these fields:

```yaml
# Homeserver connection (use Docker service name, not localhost)
homeserver:
    address: http://synapse:8008
    domain: matrix.example.com

# Appservice config
appservice:
    address: http://mautrix-whatsapp:29318   # How Synapse reaches the bridge
    hostname: 0.0.0.0
    port: 29318
    id: whatsapp                              # Unique ID for this bridge
    bot:
        username: whatsappbot
        displayname: WhatsApp bridge bot
    database:
        type: postgres
        uri: postgres://synapse:change-me-to-a-strong-password@postgres:5432/mautrix_whatsapp?sslmode=disable

# Who is allowed to use the bridge
bridge:
    permissions:
        # Allow anyone on your server to use it
        "matrix.example.com": user
        # Give yourself admin
        "@scheduler-bot:matrix.example.com": admin

# Logging
logging:
    min_level: debug
    writers:
        - type: stdout
          format: pretty-colored
```

**Important**: The `appservice.address` must be reachable from Synapse. Since both run in Docker Compose on the same network, use the container name (`mautrix-whatsapp`), not `localhost`.

### 4.3 Create the Bridge Database

The bridge needs its own PostgreSQL database (never share with Synapse). Add it to your postgres init script or create manually:

```bash
docker exec -it postgres psql -U synapse -c "CREATE DATABASE mautrix_whatsapp;"
```

### 4.4 Generate Registration File

```bash
docker run --rm -v $(pwd):/data:z dock.mau.dev/mautrix/whatsapp:latest
```

When the bridge starts and finds an existing `config.yaml`, it generates `registration.yaml` automatically if it doesn't exist, then runs. On first run, stop it after it generates the registration file.

Alternatively, you can let the bridge generate the registration on first startup -- the bridge writes `registration.yaml` to `/data/` automatically.

### 4.5 Copy Registration to Synapse

```bash
cp bridges/whatsapp/registration.yaml synapse/whatsapp-registration.yaml
```

This must match the path in `homeserver.yaml`'s `app_service_config_files` list. Then restart Synapse to pick it up.

### 4.6 Link Your WhatsApp Account

Once the bridge is running, open a chat with `@whatsappbot:matrix.example.com` (use Element or any Matrix client, or the Matrix API).

**QR Code method:**
1. Send `login qr` to the bot
2. The bot responds with a QR code image
3. Open WhatsApp on your phone > Settings > Linked Devices > Link a Device
4. Scan the QR code

**Phone number method:**
1. Send `login phone` to the bot
2. Provide your phone number when prompted
3. Enter the 8-letter code on your phone

After login, the bridge creates Matrix rooms for your WhatsApp chats and backfills recent messages (50 per chat by default).

**Note**: WhatsApp will disconnect linked devices if your phone is offline for more than 2 weeks.

---

## 5. mautrix-meta Bridge (Instagram)

The `mautrix-meta` bridge handles both Facebook Messenger and Instagram DMs, but a single instance can only serve one platform. For Instagram, configure it in `instagram` mode.

### 5.1 Generate Config

```bash
cd bridges/meta
docker run --rm -v $(pwd):/data:z dock.mau.dev/mautrix/meta:latest
```

### 5.2 Edit config.yaml

```yaml
homeserver:
    address: http://synapse:8008
    domain: matrix.example.com

appservice:
    address: http://mautrix-meta:29319    # Different port from WhatsApp
    hostname: 0.0.0.0
    port: 29319
    id: instagram                          # Unique appservice ID
    bot:
        username: instagrambot
        displayname: Instagram bridge bot
    database:
        type: postgres
        uri: postgres://synapse:change-me-to-a-strong-password@postgres:5432/mautrix_meta?sslmode=disable

bridge:
    permissions:
        "matrix.example.com": user
        "@scheduler-bot:matrix.example.com": admin

# Meta-specific: set the platform mode
network:
    mode: instagram

logging:
    min_level: debug
    writers:
        - type: stdout
          format: pretty-colored
```

The critical difference from WhatsApp: the `network.mode` field must be set to `instagram` (other options: `facebook`, `messenger`).

### 5.3 Create the Bridge Database

```bash
docker exec -it postgres psql -U synapse -c "CREATE DATABASE mautrix_meta;"
```

### 5.4 Copy Registration to Synapse

After the bridge generates `registration.yaml` on first run:

```bash
cp bridges/meta/registration.yaml synapse/meta-registration.yaml
```

Restart Synapse.

### 5.5 Log In to Instagram

The Meta bridge uses **cookie-based authentication** (not QR codes).

1. Open a DM with `@instagrambot:matrix.example.com`
2. Send `login`
3. Open a **private/incognito browser window** and log in to instagram.com
4. Open browser DevTools > Network tab
5. Filter for `graphql` requests (XHR type)
6. Right-click any `graphql` request > Copy > Copy as cURL
7. Paste the entire cURL command into the chat with the bot

The bot extracts the session cookies (`sessionid`, `csrftoken`, `mid`, `ig_did`, `ds_user_id`) and authenticates.

**Alternative**: Manually extract cookies and send as JSON:
```
login cookies {"sessionid":"abc123","csrftoken":"xyz","mid":"...","ig_did":"...","ds_user_id":"12345"}
```

**Warning**: Meta may flag your account for suspicious activity. Use a real browser session, enable 2FA, and avoid logging in from wildly different IPs.

---

## 6. mautrix-linkedin Bridge

### 6.1 Generate Config

```bash
cd bridges/linkedin
docker run --rm -v $(pwd):/data:z dock.mau.dev/mautrix/linkedin:latest
```

### 6.2 Edit config.yaml

```yaml
homeserver:
    address: http://synapse:8008
    domain: matrix.example.com

appservice:
    address: http://mautrix-linkedin:29320   # Unique port
    hostname: 0.0.0.0
    port: 29320
    id: linkedin
    bot:
        username: linkedinbot
        displayname: LinkedIn bridge bot
    database:
        type: postgres
        uri: postgres://synapse:change-me-to-a-strong-password@postgres:5432/mautrix_linkedin?sslmode=disable

bridge:
    permissions:
        "matrix.example.com": user
        "@scheduler-bot:matrix.example.com": admin

logging:
    min_level: debug
    writers:
        - type: stdout
          format: pretty-colored
```

### 6.3 Create the Bridge Database

```bash
docker exec -it postgres psql -U synapse -c "CREATE DATABASE mautrix_linkedin;"
```

### 6.4 Copy Registration to Synapse

```bash
cp bridges/linkedin/registration.yaml synapse/linkedin-registration.yaml
```

Restart Synapse.

### 6.5 Log In to LinkedIn

The LinkedIn bridge also uses cookie-based authentication, similar to the Meta bridge.

1. Open a DM with `@linkedinbot:matrix.example.com`
2. Send `login`
3. Open a **private browser window** -- use Chrome or set your User-Agent to match Chrome, as LinkedIn restricts cookies across different user agents
4. Log in to linkedin.com normally
5. Open DevTools > Network tab
6. Filter for `graphql` requests
7. Right-click a request > Copy > Copy as cURL
8. Paste the cURL command into the chat with the bot

The bot confirms login and begins syncing recent conversations.

---

## 7. Complete Docker Compose File

Save this as `docker-compose.yml` in the `matrix-server/` directory:

```yaml
services:
  # ─── Reverse Proxy ──────────────────────────────────────────
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - synapse
    networks:
      - matrix

  # ─── Matrix Homeserver ──────────────────────────────────────
  synapse:
    image: matrixdotorg/synapse:latest
    container_name: synapse
    restart: unless-stopped
    volumes:
      - ./synapse:/data
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-fSs", "http://localhost:8008/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 5s
    networks:
      - matrix

  # ─── Database ───────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: synapse
      POSTGRES_PASSWORD: change-me-to-a-strong-password
      POSTGRES_INITDB_ARGS: --encoding=UTF-8 --lc-collate=C --lc-ctype=C
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-databases.sql:/docker-entrypoint-initdb.d/init-databases.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U synapse"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - matrix

  # ─── WhatsApp Bridge ────────────────────────────────────────
  mautrix-whatsapp:
    image: dock.mau.dev/mautrix/whatsapp:latest
    container_name: mautrix-whatsapp
    restart: unless-stopped
    volumes:
      - ./bridges/whatsapp:/data
    depends_on:
      synapse:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - matrix

  # ─── Instagram Bridge (mautrix-meta in instagram mode) ─────
  mautrix-meta:
    image: dock.mau.dev/mautrix/meta:latest
    container_name: mautrix-meta
    restart: unless-stopped
    volumes:
      - ./bridges/meta:/data
    depends_on:
      synapse:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - matrix

  # ─── LinkedIn Bridge ────────────────────────────────────────
  mautrix-linkedin:
    image: dock.mau.dev/mautrix/linkedin:latest
    container_name: mautrix-linkedin
    restart: unless-stopped
    volumes:
      - ./bridges/linkedin:/data
    depends_on:
      synapse:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - matrix

volumes:
  postgres_data:
  caddy_data:
  caddy_config:

networks:
  matrix:
    driver: bridge
```

### Database Init Script

Create `init-databases.sql` to automatically create bridge databases on first PostgreSQL start:

```sql
CREATE DATABASE mautrix_whatsapp;
CREATE DATABASE mautrix_meta;
CREATE DATABASE mautrix_linkedin;
```

### Bootstrap Sequence

The order matters because bridges need their config files before starting, and Synapse needs registration files:

```bash
# 1. Generate Synapse config (if not already done)
docker run -it --rm \
    -v $(pwd)/synapse:/data \
    -e SYNAPSE_SERVER_NAME=matrix.example.com \
    -e SYNAPSE_REPORT_STATS=no \
    matrixdotorg/synapse:latest generate

# 2. Edit synapse/homeserver.yaml (database, listeners, registration_shared_secret,
#    app_service_config_files -- see Section 2)

# 3. Start just postgres first
docker compose up -d postgres

# 4. Generate bridge configs (each bridge writes config.yaml on first run, then exits)
docker run --rm -v $(pwd)/bridges/whatsapp:/data:z dock.mau.dev/mautrix/whatsapp:latest
docker run --rm -v $(pwd)/bridges/meta:/data:z dock.mau.dev/mautrix/meta:latest
docker run --rm -v $(pwd)/bridges/linkedin:/data:z dock.mau.dev/mautrix/linkedin:latest

# 5. Edit each bridge's config.yaml (see Sections 4, 5, 6)

# 6. Start Synapse (without bridges, to create the registration files)
docker compose up -d synapse

# 7. Start bridges briefly to generate registration.yaml files
#    They'll connect to Synapse on the Docker network
docker compose up -d mautrix-whatsapp mautrix-meta mautrix-linkedin

# 8. Wait a few seconds for registration files to be generated, then copy them
cp bridges/whatsapp/registration.yaml synapse/whatsapp-registration.yaml
cp bridges/meta/registration.yaml synapse/meta-registration.yaml
cp bridges/linkedin/registration.yaml synapse/linkedin-registration.yaml

# 9. Restart Synapse to load the registration files
docker compose restart synapse

# 10. Restart bridges (they may have failed while Synapse didn't know about them yet)
docker compose restart mautrix-whatsapp mautrix-meta mautrix-linkedin

# 11. Start Caddy
docker compose up -d caddy

# 12. Create your admin user
docker exec -it synapse register_new_matrix_user \
    http://localhost:8008 -c /data/homeserver.yaml \
    -u scheduler-bot -p 'a-strong-password' -a

# 13. Check everything is running
docker compose ps
```

After the initial bootstrap, a simple `docker compose up -d` brings everything up in the right order.

---

## 8. Common Gotchas

### Registration files not found

**Symptom**: Synapse fails to start with "Failed to read appservice registration file" errors.

**Fix**: Make sure the paths in `app_service_config_files` in `homeserver.yaml` match where you actually copied the files. Inside the Synapse container, the volume is mounted at `/data`, so paths should be `/data/whatsapp-registration.yaml` etc.

### `localhost` doesn't work in Docker

**Symptom**: Bridge logs show "connection refused" errors when trying to reach Synapse.

**Fix**: Inside Docker, `localhost` refers to the container itself. Use Docker service names: `http://synapse:8008` for the homeserver address, `http://mautrix-whatsapp:29318` for the bridge appservice address.

### Port conflicts between bridges

**Symptom**: Second bridge fails to start with "address already in use."

**Fix**: Each bridge must have a unique `appservice.port`. This guide uses 29318 (WhatsApp), 29319 (Meta), 29320 (LinkedIn). Also ensure each bridge has a unique `appservice.id`.

### Bridge bot rejects DM invites

**Symptom**: You invite `@whatsappbot:matrix.example.com` but get no response or the invite is rejected.

**Fix**: Check `bridge.permissions` in the bridge's `config.yaml`. Your Matrix user ID (or your homeserver domain) must be listed with at least `user` permission. After changing permissions, restart the bridge.

### Registration file gets regenerated / tokens change

**Symptom**: After updating bridge config and restarting, Synapse rejects the bridge with "Invalid appservice token."

**Fix**: If you change `homeserver.domain`, `appservice.address`, `appservice.id`, or token fields in a bridge's `config.yaml`, the `registration.yaml` is regenerated with new tokens. You must re-copy it to Synapse's data directory and restart Synapse.

### Database "already exists" or "does not exist"

**Symptom**: Bridge fails with database connection errors.

**Fix**: The `init-databases.sql` script only runs on the very first PostgreSQL startup (when the data volume is empty). If you added it after Postgres already initialized, create the databases manually:

```bash
docker exec -it postgres psql -U synapse -c "CREATE DATABASE mautrix_whatsapp;"
docker exec -it postgres psql -U synapse -c "CREATE DATABASE mautrix_meta;"
docker exec -it postgres psql -U synapse -c "CREATE DATABASE mautrix_linkedin;"
```

### Synapse UID/GID permission issues

**Symptom**: Synapse or bridge containers fail with permission errors on `/data`.

**Fix**: The Synapse Docker image runs as UID 991 by default. The mautrix bridge images `chown` their `/data` to UID 1337. If you're running on a system with strict permissions, you may need to adjust ownership:

```bash
# For Synapse data directory
sudo chown -R 991:991 synapse/

# For bridge data directories
sudo chown -R 1337:1337 bridges/whatsapp/ bridges/meta/ bridges/linkedin/
```

### WhatsApp disconnects after 2 weeks

**Symptom**: Bridge stops receiving messages; logs show "no phone data received."

**Cause**: WhatsApp requires the linked phone to come online at least once every ~14 days. If it doesn't, the linked device (the bridge) is disconnected.

**Fix**: Make sure the phone with WhatsApp is regularly connected to the internet. Re-link if disconnected by sending `login qr` again.

### Meta/LinkedIn session expires

**Symptom**: Instagram or LinkedIn bridge stops working; logs show authentication errors.

**Cause**: Cookie-based sessions expire or get invalidated by the platform (password change, security review, etc.).

**Fix**: Re-authenticate by sending `login` to the bridge bot and repeating the cookie extraction process.

### `x_forwarded: true` not set

**Symptom**: Synapse logs show all requests coming from the reverse proxy IP instead of real client IPs, or rate-limiting is too aggressive.

**Fix**: Add `x_forwarded: true` to the listener in `homeserver.yaml` (see Section 2.4).

---

## 9. Verifying It Works

### 9.1 Check All Containers Are Running

```bash
docker compose ps
```

All services should show `Up (healthy)` or `Up`.

### 9.2 Check Synapse Health

```bash
curl -s http://localhost:8008/health
# Expected: OK
```

### 9.3 Check Bridge Logs

```bash
# Look for "Bridge started" or similar success messages
docker compose logs mautrix-whatsapp --tail 20
docker compose logs mautrix-meta --tail 20
docker compose logs mautrix-linkedin --tail 20
```

Healthy bridge output includes lines like:
- `Starting bridge`
- `Bridge initialized`
- `Appservice listener running on 0.0.0.0:29318`

### 9.4 Verify Appservice Registration

Use the Synapse admin API to check registered appservices:

```bash
# List joined rooms for the bridge bot to confirm it exists
curl -s -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
    "https://matrix.example.com/_matrix/client/v3/joined_rooms" | jq .
```

### 9.5 Test Message Flow (WhatsApp Example)

1. **Login**: Send `login qr` to `@whatsappbot:matrix.example.com` via Element or the API
2. **Scan QR**: Link your WhatsApp
3. **Wait**: The bridge creates rooms for your WhatsApp chats (takes ~1 minute)
4. **Send a test message**: Have someone send you a WhatsApp message
5. **Verify in Matrix**: The message should appear in the corresponding Matrix room

To verify via the API:

```bash
# List rooms (should include WhatsApp chat rooms)
curl -s -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
    "https://matrix.example.com/_matrix/client/v3/joined_rooms" | jq .

# Sync to get recent messages
curl -s -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
    "https://matrix.example.com/_matrix/client/v3/sync?timeout=5000" | jq '.rooms.join | keys'
```

### 9.6 Test Message Flow (Instagram Example)

1. **Login**: Send `login` to `@instagrambot:matrix.example.com`
2. **Extract cookies**: Follow the cURL-copy flow described in Section 5.5
3. **Wait**: Bridge syncs recent Instagram DM conversations
4. **Send a test message**: Have someone DM you on Instagram
5. **Verify**: Message appears in the Matrix room

### 9.7 Test Message Flow (LinkedIn Example)

1. **Login**: Send `login` to `@linkedinbot:matrix.example.com`
2. **Extract cookies**: Follow the cURL-copy flow described in Section 6.5
3. **Wait**: Bridge syncs recent LinkedIn conversations
4. **Send a test message**: Have someone message you on LinkedIn
5. **Verify**: Message appears in the Matrix room

### 9.8 Programmatic Verification

For automated checks (useful in CI or monitoring):

```bash
#!/usr/bin/env bash
set -e
TOKEN="YOUR_ACCESS_TOKEN"
BASE="https://matrix.example.com"

echo "--- Synapse health ---"
curl -sf "$BASE/health" && echo " OK"

echo "--- Whoami ---"
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/_matrix/client/v3/account/whoami" | jq .

echo "--- Joined rooms ---"
curl -sf -H "Authorization: Bearer $TOKEN" "$BASE/_matrix/client/v3/joined_rooms" | jq '.joined_rooms | length' | xargs echo "Room count:"

echo "--- Bridge bot profiles ---"
for bot in whatsappbot instagrambot linkedinbot; do
    echo -n "$bot: "
    curl -sf -H "Authorization: Bearer $TOKEN" \
        "$BASE/_matrix/client/v3/profile/@${bot}:matrix.example.com/displayname" | jq -r '.displayname // "NOT FOUND"'
done
```

---

## References

- [Synapse Docker README](https://github.com/element-hq/synapse/blob/develop/docker/README.md)
- [Synapse Reverse Proxy docs](https://element-hq.github.io/synapse/latest/reverse_proxy.html)
- [mautrix Bridge Docker Setup](https://docs.mau.fi/bridges/general/docker-setup.html)
- [mautrix Initial Bridge Config](https://docs.mau.fi/bridges/general/initial-config.html)
- [mautrix Registering Appservices](https://docs.mau.fi/bridges/general/registering-appservices.html)
- [mautrix-whatsapp docs](https://docs.mau.fi/bridges/go/whatsapp/)
- [mautrix-meta docs](https://docs.mau.fi/bridges/go/meta/)
- [mautrix-linkedin repo](https://github.com/mautrix/linkedin)
- [Synapse Admin API](https://matrix-org.github.io/synapse/latest/usage/administration/admin_api/index.html)
