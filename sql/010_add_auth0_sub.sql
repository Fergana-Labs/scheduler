ALTER TABLE users ADD COLUMN auth0_sub TEXT;
CREATE UNIQUE INDEX idx_users_auth0_sub ON users (auth0_sub) WHERE auth0_sub IS NOT NULL;
