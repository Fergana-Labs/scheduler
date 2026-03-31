-- Backfill google_email for existing connected users where it matches their signup email.
-- The 4 known mismatched users should be updated manually BEFORE running this migration.
UPDATE users SET google_email = email
WHERE google_refresh_token IS NOT NULL AND google_email IS NULL;
