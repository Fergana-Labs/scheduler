-- Audit log for every weekly guide-updater run per user per guide.
-- proposed_changes: all changes the agent wanted to make (JSON array)
-- applied_changes:  subset that passed the frequency gate and were written
-- skipped_reason:   set when the run was skipped (e.g. too few edited drafts)
CREATE TABLE guide_update_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ran_at TIMESTAMPTZ DEFAULT now(),
    guide_name TEXT NOT NULL,
    drafts_analyzed INT NOT NULL DEFAULT 0,
    changes_made BOOLEAN NOT NULL DEFAULT FALSE,
    proposed_changes JSONB NOT NULL DEFAULT '[]',
    applied_changes JSONB NOT NULL DEFAULT '[]',
    skipped_reason TEXT,
    agent_log TEXT
);
CREATE INDEX idx_guide_update_runs_user ON guide_update_runs(user_id);
CREATE INDEX idx_guide_update_runs_ran_at ON guide_update_runs(ran_at);
CREATE INDEX idx_guide_update_runs_guide ON guide_update_runs(guide_name);
