-- Auth schema for users
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE auth.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    avatar_url TEXT,
    data JSONB DEFAULT '{}',           -- Flexible metadata
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for email lookup
CREATE INDEX idx_users_email ON auth.users(email);

-- Grant access to app role
GRANT USAGE ON SCHEMA auth TO substrate_app;
GRANT SELECT, INSERT, UPDATE ON auth.users TO substrate_app;
