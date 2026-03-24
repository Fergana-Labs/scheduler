ALTER TABLE users ADD COLUMN matrix_homeserver_url TEXT;
ALTER TABLE users ADD COLUMN matrix_access_token TEXT;
ALTER TABLE users ADD COLUMN matrix_user_id TEXT;
ALTER TABLE users ADD COLUMN matrix_sync_enabled BOOLEAN NOT NULL DEFAULT false;
