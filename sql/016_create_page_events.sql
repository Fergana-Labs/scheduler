-- Lightweight anonymous page event tracking (no user_id required)
CREATE TABLE page_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_page_events_event ON page_events(event);
CREATE INDEX idx_page_events_created ON page_events(created_at);
