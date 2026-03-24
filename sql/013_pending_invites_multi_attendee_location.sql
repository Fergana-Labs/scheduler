-- Rename attendee_email to attendee_emails (now stores a JSON array)
-- and add location field to pending_invites.

ALTER TABLE pending_invites RENAME COLUMN attendee_email TO attendee_emails;
ALTER TABLE pending_invites ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT '';
