-- Email inboxes - maps email addresses to users
CREATE TABLE auth.inboxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,        -- e.g. "support@yourdomain.com"
    name TEXT,                         -- Display name, e.g. "Support Team"
    is_default BOOLEAN DEFAULT false,  -- Default inbox for user
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_inboxes_user ON auth.inboxes(user_id);
CREATE INDEX idx_inboxes_email ON auth.inboxes(email);

-- Grant to app role
GRANT SELECT, INSERT, UPDATE, DELETE ON auth.inboxes TO substrate_app;

-- Helper function: get user_id for an email address
CREATE OR REPLACE FUNCTION auth.user_for_email(p_email TEXT) RETURNS UUID AS $$
  SELECT user_id FROM auth.inboxes WHERE email = p_email LIMIT 1;
$$ LANGUAGE sql STABLE;

GRANT EXECUTE ON FUNCTION auth.user_for_email(TEXT) TO substrate_app;
