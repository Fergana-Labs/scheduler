# Third-Party Bot Mode

## Overview

A new product mode where users CC a shared email address (e.g. scheduling@tryscheduled.com) to delegate meeting scheduling to a third-party bot. Instead of watching each user's inbox and creating drafts for review, one bot account receives CC'd emails, checks the user's calendar, and replies directly from its own address.

**Why this is better:**
- Users only grant calendar access (no inbox read/compose) — dramatically lower trust barrier
- No draft approval step — the bot IS a third party, so sending its own emails is natural
- One inbox to watch instead of N per-user Pub/Sub watches — simpler infrastructure
- Simpler onboarding — connect calendar, start CC'ing the bot
- Like Calendly, but conversational and aware of the user's real calendar

## How It Works (User Perspective)

1. User signs up, connects Google Calendar (calendar-only OAuth)
2. User optionally configures preferences (meeting durations, preferred times, buffer)
3. When user wants help scheduling, they CC scheduling@tryscheduled.com on an email thread
4. Bot receives the email, identifies the user, checks their calendar
5. Bot replies-all from scheduling@tryscheduled.com: "Hi, I'm Scheduled, Henry's scheduling assistant. Here are some times that work for him..."
6. Recipient picks a time (via reply or scheduling link)
7. Bot confirms and creates the calendar event
8. User sees the whole conversation in their inbox (they're CC'd throughout)

## Architecture Changes

### Current Architecture
```
User's Gmail ──[Pub/Sub per user]──> Control Plane ──> Classify ──> Draft Agent ──> Draft in User's Gmail
                                         │
                                    User's Gmail creds
                                    User's Calendar creds
```

### New Architecture
```
Any email thread ──[User CCs bot]──> Bot's Gmail ──[Single Pub/Sub]──> Control Plane
                                                                            │
                                                                    Identify user from CC
                                                                    Load user's Calendar creds
                                                                            │
                                                                    Bot Reply Agent
                                                                            │
                                                                    Send from bot's Gmail
```

## Component-Level Changes

### 1. Bot Gmail Account (NEW)

**What:** A Google Workspace account at scheduling@tryscheduled.com that receives and sends all bot emails.

**Setup:**
- Google Workspace account with proper SPF/DKIM/DMARC for deliverability
- Bot OAuth credentials stored as env vars (`BOT_GMAIL_REFRESH_TOKEN`, `BOT_GMAIL_CLIENT_ID`, etc.)
- Single Pub/Sub topic + subscription for the bot inbox
- One `gmail.watch()` call instead of N

**New env vars:**
```
BOT_EMAIL=scheduling@tryscheduled.com
BOT_GMAIL_REFRESH_TOKEN=...
BOT_GMAIL_PUBSUB_TOPIC=projects/.../topics/bot-gmail-push
```

**New code:**
- `src/scheduler/bot/gmail.py` — Bot-specific Gmail client (or reuse `GmailClient` with bot creds)
- Singleton bot credentials loader (no per-user credential management for email)

### 2. Auth Flow (MODIFIED)

**Current scopes** (`auth/google_auth.py`):
```python
SCOPES = [
    "gmail.readonly",    # Remove
    "gmail.compose",     # Remove
    "calendar",          # Keep (or downgrade to calendar.readonly)
    "userinfo.email",    # Keep
]
```

**New scopes for bot mode:**
```python
BOT_MODE_SCOPES = [
    "calendar.readonly",     # Read user's calendar for availability
    "userinfo.email",        # Identify the user
]
```

Calendar write access is only needed if we want to create events on the user's calendar when a meeting is confirmed. If so, keep `calendar` (read/write). If we create events from the bot's own calendar and invite the user, `calendar.readonly` suffices.

**Files:** `src/scheduler/auth/google_auth.py`, `src/scheduler/controlplane/server.py` (OAuth callback routes)

### 3. Email Webhook & Processing Pipeline (MODIFIED)

**Current flow** (`server.py:2680-2677`):
1. Pub/Sub notification arrives with user's email address
2. Look up user by email
3. Fetch new messages from user's inbox via History API
4. For each message: classify intent → compose draft

**New flow:**
1. Pub/Sub notification arrives for bot inbox
2. Fetch new messages from bot's inbox via History API
3. For each message:
   a. Parse From/To/CC headers to identify which registered user CC'd the bot
   b. If no registered user found → auto-reply "Sign up at tryscheduled.com"
   c. If registered user → load their calendar creds
   d. Skip intent classification (user explicitly CC'd the bot — intent is clear)
   e. Extract entities: who's the meeting with, how long, any constraints
   f. Check user's calendar for availability
   g. Reply-all from bot account with proposed times + scheduling link

**What gets removed:**
- `_gmail_poll_loop()` — per-user polling (replaced by single bot poll)
- `_watch_renewal_loop()` — per-user watch renewal (replaced by single bot watch)
- `_draft_refresh_loop()` — no more drafts to refresh
- Per-user `_get_new_message_ids()` — single bot history tracking
- Newsletter/mass email filtering — bot only gets CC'd emails, not user's whole inbox
- Most of `_process_message_batch()` — rewritten for bot flow

**New function:** `_process_bot_messages(message_ids)` — the new pipeline:
```python
def _process_bot_messages(message_ids: list[str]):
    bot_gmail = get_bot_gmail_client()
    for message_id in message_ids:
        email = bot_gmail.get_email(message_id)

        # Identify which registered user CC'd us
        user = identify_user_from_headers(email)
        if not user:
            bot_gmail.send_reply(email, "I don't recognize you yet. Sign up at...")
            continue

        # Check if this is a follow-up in an existing conversation
        conversation = get_or_create_conversation(user.id, email.thread_id)

        # Load user's calendar
        calendar = load_user_calendar(user)

        # Run bot reply agent
        reply_agent.compose_and_send(
            bot_gmail=bot_gmail,
            calendar=calendar,
            email=email,
            conversation=conversation,
            user=user,
        )
```

**Files:** `src/scheduler/controlplane/server.py`

### 4. User Identification (NEW)

**Logic:** When an email arrives in the bot inbox, determine which registered user is involved.

```python
def identify_user_from_headers(email) -> User | None:
    """Find the registered user who CC'd the bot.

    Check order:
    1. From address (user sent the email, CC'd the bot)
    2. To/CC addresses (someone else CC'd the bot, user is a recipient)

    If multiple registered users are found, prefer the one in From.
    """
    all_addresses = parse_all_addresses(email.sender, email.recipient, email.cc)
    # Remove the bot's own address
    all_addresses.discard(BOT_EMAIL)

    # Check From first — the person who CC'd us is most likely the user
    from_addr = parse_email_address(email.sender)
    user = get_user_by_email(from_addr)
    if user:
        return user

    # Check To/CC — maybe someone else CC'd us on a thread with our user
    for addr in all_addresses:
        user = get_user_by_email(addr)
        if user:
            return user

    return None
```

**Edge cases:**
- Unregistered user CCs the bot → auto-reply with signup link
- Multiple registered users in the thread → check the one who CC'd the bot (From or most recent CC-er)
- Someone forwards the bot an email (not CC) → same logic applies
- Bot receives spam → rate limit auto-replies to unknown senders

**Files:** New `src/scheduler/bot/identity.py`

### 5. Bot Reply Agent (MODIFIED from `drafts/composer.py`)

**Current agent identity:** "You are a draft composer agent for a scheduling assistant. Your job is to read the email thread, check the user's calendar for availability, and compose a natural-sounding draft reply."

**New agent identity:**
```
You are Scheduled, a scheduling assistant acting on behalf of {user_name} ({user_email}).
You communicate directly with the people {user_name} is scheduling with.

You received this email because {user_name} CC'd you on a thread. Your job is to:
1. Read the thread to understand what's being scheduled
2. Check {user_name}'s calendar for availability
3. Reply with proposed times or confirm a time

Always identify yourself: "Hi, I'm Scheduled, {user_name}'s scheduling assistant."
Keep replies concise and friendly. You are a professional third-party assistant, not
pretending to be {user_name}.
```

**Tool changes:**
| Current Tool | Bot Mode |
|-------------|----------|
| `create_draft` | Remove — replaced by `send_reply` |
| `send_email` (autopilot only) | `send_reply` — always available, sends from bot account |
| `read_thread` | Keep — reads from bot's inbox copy |
| `get_calendar_events` | Keep — uses user's calendar creds |
| `load_guide` (style) | Remove — bot has its own voice |
| `load_guide` (preferences) | Keep — still useful for scheduling preferences |
| `propose_invite` | Modify — bot creates the invite directly when confirmed |
| `get_booking_page_times` | Keep |
| `book_meeting_slot` | Keep |

**New tools:**
- `send_reply` — sends from bot account, reply-all to thread, keeps user in CC
- `get_conversation_state` — retrieves what was previously proposed/declined in this thread
- `escalate_to_user` — sends a private email to the user asking for guidance

**Files:** New `src/scheduler/bot/agent.py` (or heavily modify `drafts/composer.py`)

### 6. Multi-Turn Conversation State Machine (NEW)

This is the biggest new complexity. Currently, multi-turn is handled by the user (they review each draft). Now the bot handles it.

**States:**
```
new → proposing → negotiating → confirmed → done
                      ↓
                  escalated (bot asked user for help)
                      ↓
                  cancelled
```

**State transitions:**
- `new`: Bot just received the first CC. Reads thread, proposes times.
- `proposing`: Bot sent proposed times, waiting for reply.
- `negotiating`: Recipient replied (declined times, counterproposed, asked questions). Bot adjusts.
- `confirmed`: A time was agreed upon. Bot creates calendar event.
- `done`: Event created, conversation complete.
- `escalated`: Bot wasn't sure what to do, asked the user privately.
- `cancelled`: Meeting cancelled or thread went cold (timeout).

**Conversation memory per thread:**
```json
{
  "proposed_windows": [{"date": "2026-04-03", "start": "10:00", "end": "10:30"}],
  "declined_windows": [{"date": "2026-04-02", "start": "14:00", "end": "14:30"}],
  "constraints": ["recipient prefers mornings", "no Fridays"],
  "turn_count": 3,
  "last_bot_reply_at": "2026-04-01T15:00:00Z"
}
```

The agent receives this state as context on each turn so it doesn't re-propose declined times or ignore stated constraints.

**Timeout policy:** If no reply for 48 hours in `negotiating` state, bot sends a gentle follow-up. After 7 days, auto-close the conversation.

**Files:** New `src/scheduler/bot/conversation.py`

### 7. Database Schema Changes

```sql
-- New table: bot conversation state
CREATE TABLE bot_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    thread_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'new',
    participants TEXT[] NOT NULL DEFAULT '{}',
    proposed_windows JSONB DEFAULT '[]',
    declined_windows JSONB DEFAULT '[]',
    constraints JSONB DEFAULT '[]',
    event_summary TEXT,
    duration_minutes INT,
    turn_count INT DEFAULT 0,
    last_bot_reply_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    UNIQUE(user_id, thread_id)
);

-- New table: bot account state (single row)
CREATE TABLE bot_account (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    gmail_history_id TEXT,
    watch_expiration BIGINT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- users table modifications:
-- Add: scheduling_mode TEXT DEFAULT 'bot' (or 'draft' for legacy)
-- gmail_history_id becomes nullable (not needed for bot mode users)
-- google_refresh_token still needed (for calendar), but scopes change
```

**Migration:** Add new tables, add `scheduling_mode` column to users. Existing users default to `'draft'` mode. New signups default to `'bot'` mode.

**Files:** New migration in `sql/`, modify `src/scheduler/db.py` and `src/scheduler/db_postgres.py`

### 8. Onboarding (SIMPLIFIED)

**Current onboarding** (runs 3 agents in parallel):
1. Backfill agent — searches 60 days of Gmail for agreed meetings → Remove
2. Preferences agent — analyzes calendar + emails for scheduling patterns → Keep (calendar-only)
3. Style agent — analyzes past emails for writing style → Remove (bot has own voice)

**New onboarding:**
1. User signs up, grants Calendar-only OAuth
2. Preferences agent reads calendar patterns (preferred times, durations, buffer)
3. Done. Show user: "CC scheduling@tryscheduled.com when you need help scheduling."

Much faster onboarding. No Gmail access needed. Preferences agent can still learn a lot from calendar data alone (when do meetings happen, how long, how much buffer, which days are packed).

**Files:** `src/scheduler/onboarding/agent.py`, `src/scheduler/guides/preferences.py`

### 9. Background Loops (SIMPLIFIED)

**Remove:**
- `_gmail_poll_loop()` — per-user Gmail polling
- `_watch_renewal_loop()` — per-user watch renewal
- `_draft_refresh_loop()` — draft staleness management

**Add:**
- `_bot_inbox_poll_loop()` — single bot inbox poll (fallback if no Pub/Sub)
- `_bot_watch_renewal()` — single watch renewal (runs inside existing maintenance loop)
- `_conversation_timeout_loop()` — close stale conversations, send follow-ups

**Files:** `src/scheduler/controlplane/server.py`

### 10. Frontend (MODIFIED)

**Remove:**
- Draft management UI (no more drafts)

**Add:**
- Active conversations dashboard: list of threads the bot is managing
- Conversation detail: see the full thread, what the bot said, current state
- Ability to intervene: "take over this conversation" or "tell them I'm unavailable"

**Simplify:**
- Settings: fewer toggles (no autopilot toggle — bot always sends, no draft-related settings)
- Onboarding: shorter flow, just calendar connection

**Keep:**
- Scheduling links pages (recipients clicking links to pick times)
- Calendar selection (which calendars to check for conflicts)
- Preferences editing

**Files:** `web/` Next.js app

### 11. Email Deliverability (NEW concern)

The bot sends from scheduling@tryscheduled.com. Deliverability matters more than before because the bot IS the sender (not creating drafts in user's own Gmail).

**Required:**
- Google Workspace account (not regular Gmail — higher sending limits, better deliverability)
- SPF record for tryscheduled.com authorizing Google's servers
- DKIM signing via Google Workspace
- DMARC policy
- Warm up the sending domain gradually (start with small volume)
- Monitor bounce rates and spam complaints
- "Unsubscribe" or "Stop managing this thread" option in bot emails

### 12. Scheduling Links (KEEP, minor changes)

The existing scheduling links system works well for this model and gets even more useful:

- Bot includes a scheduling link in every proposal email
- Recipient can click the link instead of replying
- When recipient picks a time via link, bot auto-confirms and creates the event

**Minor change:** Link creation currently tied to draft composition. Decouple it so it works with bot replies. The `_create_scheduling_link_for_draft` function becomes `_create_scheduling_link_for_reply`.

## Design Decisions to Make

### 1. Both modes or replace?

**Option A — Bot mode only (replace draft mode)**
- Simpler codebase, one path
- Breaks existing users' workflow
- Clean product story

**Option B — Both modes, user chooses**
- More complex but non-breaking
- Users pick during onboarding: "Draft mode" vs "Bot mode"
- `users.scheduling_mode` column routes to different pipelines
- Shared calendar infra, different email flows

**Decision:** Option B — keep both modes. Existing users keep draft mode. New signups can choose bot mode. Remove draft mode later once bot mode is proven.

### 2. Calendar event creation

**Decision:** Bot sends calendar invite from its own account (like Calendly). User only needs `calendar.readonly`. User receives invite like any other meeting — familiar flow.

### 3. When to escalate to the user

**Decision:** Only escalate when genuinely unsure (ambiguous email, question only user can answer). Do NOT escalate for long back-and-forth — that's where this product is most beneficial.

### 4. How does the user intervene?

**Decision:** Bot emails the user to ask when it needs guidance. User can also reply in the thread to take over.

### 5. What if someone replies to the bot directly?

If someone emails scheduling@tryscheduled.com directly (not as a CC on a thread with a registered user), the bot should reply:
- "Hi! I help schedule meetings when someone CCs me on a thread. To get started, ask [person] to CC me, or sign up at tryscheduled.com to use me yourself."

## Phased Implementation

### Phase 1: Bot Account + Identity Resolution (1-2 weeks)

- Set up Google Workspace account for scheduling@tryscheduled.com
- Email deliverability: SPF, DKIM, DMARC
- Bot Gmail credentials management (env vars, singleton client)
- Single Pub/Sub watch on bot inbox
- New webhook handler for bot inbox notifications
- User identification from email headers
- Auto-reply for unregistered users
- Database: `bot_account` table, `bot_conversations` table

**Testable milestone:** Bot receives a CC'd email and correctly identifies the registered user.

### Phase 2: Calendar-Only Auth + Bot Reply Agent (1-2 weeks)

- New OAuth flow with calendar-only scopes
- Modified agent: sends from bot account, new system prompt
- Basic reply: read thread, check calendar, propose times, send reply
- Include scheduling link in bot replies
- Single-turn only (no multi-turn negotiation yet)

**Testable milestone:** CC the bot on an email → bot replies with available times from your calendar.

### Phase 3: Multi-Turn Conversations (2-3 weeks)

- Conversation state machine (new → proposing → negotiating → confirmed)
- Track proposed/declined windows per thread
- Handle counterproposals and declines
- User intervention detection (user replies in thread → bot steps back)
- Confirmation flow: create calendar event when time is agreed
- Conversation timeout and follow-ups

**Testable milestone:** Full back-and-forth negotiation ending in a confirmed calendar event.

### Phase 4: Dashboard + Notifications (1-2 weeks)

- Frontend: active conversations list
- Frontend: conversation detail view
- Frontend: "take over" / "cancel" actions
- Email notifications to user when bot acts (optional, configurable)
- Escalation: bot emails user privately when uncertain

**Testable milestone:** User can see and manage all active bot conversations from the web app.

### Phase 5: Polish + Migration (1-2 weeks)

- Both modes supported (`scheduling_mode` column)
- Existing users keep draft mode, new users default to bot mode
- Settings UI for switching modes
- Simplified onboarding for bot mode
- Rate limiting and quota management for bot account
- Monitoring and alerting for bot email deliverability

**Testable milestone:** New user signs up, connects calendar, CCs the bot, meeting gets scheduled — full loop.

## What We Can Delete

Once bot mode is the primary path (and draft mode is legacy/deprecated):

- `_gmail_poll_loop()` — per-user polling
- `_watch_renewal_loop()` — per-user watch renewal
- `_draft_refresh_loop()` — draft staleness
- `gmail.compose` scope
- `gmail.readonly` scope
- Draft creation/deletion/refresh logic
- Email style guide writer (`guides/style.py`)
- Gmail backfill onboarding agent
- Newsletter/mass email classifier (`classifier/newsletter.py`)
- `composed_drafts` table (eventually)
- `pending_invites` table (bot handles invites directly)
- Most of `_process_message_batch()` in server.py

## Risks

1. **Email deliverability** — If scheduling@tryscheduled.com gets flagged as spam, the whole product breaks. Mitigation: proper DNS records, gradual warm-up, monitor reputation.

2. **Gmail API quotas** — One account sending for all users. At scale, may hit limits. Mitigation: Google Workspace has higher limits; can use multiple bot accounts with round-robin.

3. **Bot says something wrong** — No human review before send. Mitigation: conservative agent behavior, escalation for ambiguous cases, user can always jump in.

4. **Threading edge cases** — Gmail threading is complex (forwarded threads, subject line changes). Mitigation: robust thread ID tracking, handle gracefully when threading breaks.

5. **Multi-user coordination** — When both parties in a thread are Scheduled users, the bot could talk to itself. Mitigation: detect this case, only act on behalf of the CC-er.
