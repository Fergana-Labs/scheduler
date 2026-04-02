-- Add a status column so in-flight runs are visible in the admin UI.
-- Values: 'running' | 'done' | 'skipped' | 'failed'
-- Existing rows are all completed; backfill based on skipped_reason.

ALTER TABLE guide_update_runs
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'done';

UPDATE guide_update_runs
   SET status = 'skipped'
 WHERE skipped_reason IS NOT NULL AND status = 'done';
