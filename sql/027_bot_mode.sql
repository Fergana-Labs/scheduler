-- Third-party bot mode: bot conversations, bot account state, user scheduling mode

-- Track which scheduling mode each user is in (draft = existing, bot = new CC-based)
ALTER TABLE users ADD COLUMN IF NOT EXISTS scheduling_mode TEXT NOT NULL DEFAULT 'draft';

-- Single-row table for the bot Gmail account state
CREATE TABLE IF NOT EXISTS bot_account (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    gmail_history_id TEXT,
    watch_expiration BIGINT,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Insert the singleton row if it doesn't exist
INSERT INTO bot_account (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Active bot conversations (one per user+thread)
CREATE TABLE IF NOT EXISTS bot_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thread_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'new',
    participants TEXT[] NOT NULL DEFAULT '{}',
    counterparty_email TEXT,
    event_summary TEXT,
    duration_minutes INT,
    proposed_windows JSONB NOT NULL DEFAULT '[]',
    declined_windows JSONB NOT NULL DEFAULT '[]',
    constraints JSONB NOT NULL DEFAULT '[]',
    turn_count INT NOT NULL DEFAULT 0,
    last_bot_reply_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    UNIQUE(user_id, thread_id)
);

CREATE INDEX IF NOT EXISTS idx_bot_conversations_user ON bot_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_bot_conversations_state ON bot_conversations(state);
CREATE INDEX IF NOT EXISTS idx_bot_conversations_updated ON bot_conversations(updated_at);

-- Track messages the bot has already processed (separate from per-user processed_messages)
CREATE TABLE IF NOT EXISTS bot_processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ DEFAULT now()
);
