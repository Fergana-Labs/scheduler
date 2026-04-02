-- Track every write to guides so changes can be reviewed and rolled back.
-- source values: 'onboarding', 'updater', 'manual', 'regenerate'
CREATE TABLE guide_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_guide_versions_user_name ON guide_versions(user_id, name);
CREATE INDEX idx_guide_versions_created ON guide_versions(created_at);
