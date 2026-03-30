CREATE TABLE IF NOT EXISTS self_hosted_registrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    registered_at   TIMESTAMP NOT NULL DEFAULT now()
);
