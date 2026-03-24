CREATE TABLE IF NOT EXISTS pending_replies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    platform TEXT NOT NULL,
    room_id TEXT NOT NULL,
    sender_name TEXT NOT NULL,
    conversation_context JSONB,
    proposed_reply TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX idx_pending_replies_user_status ON pending_replies(user_id, status);
