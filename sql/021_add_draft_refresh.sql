-- Track how many times a draft has been refreshed (stale draft → recomposed with new times).
ALTER TABLE composed_drafts ADD COLUMN IF NOT EXISTS refresh_count INT NOT NULL DEFAULT 0;

-- Store the proposed time windows so we can check if they've become stale.
-- Format: [{"date": "YYYY-MM-DD", "start": "HH:MM", "end": "HH:MM"}, ...]
ALTER TABLE composed_drafts ADD COLUMN IF NOT EXISTS suggested_windows JSONB NOT NULL DEFAULT '[]';
