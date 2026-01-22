-- Shared inboxes - many-to-many between users and inboxes

-- Remove user_id from inboxes (inbox can be shared)
ALTER TABLE auth.inboxes DROP COLUMN IF EXISTS user_id;
ALTER TABLE auth.inboxes DROP COLUMN IF EXISTS is_default;

-- Junction table for inbox access
CREATE TABLE auth.inbox_members (
    inbox_id UUID NOT NULL REFERENCES auth.inboxes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',        -- 'owner', 'member', 'viewer'
    is_default BOOLEAN DEFAULT false,  -- User's default inbox for sending
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (inbox_id, user_id)
);

CREATE INDEX idx_inbox_members_user ON auth.inbox_members(user_id);

-- Grant to app role
GRANT SELECT, INSERT, UPDATE, DELETE ON auth.inbox_members TO substrate_app;

-- Update helper: get all user_ids who can access an inbox
CREATE OR REPLACE FUNCTION auth.users_for_email(p_email TEXT) RETURNS SETOF UUID AS $$
  SELECT im.user_id
  FROM auth.inboxes i
  JOIN auth.inbox_members im ON im.inbox_id = i.id
  WHERE i.email = p_email;
$$ LANGUAGE sql STABLE;

GRANT EXECUTE ON FUNCTION auth.users_for_email(TEXT) TO substrate_app;

-- Migrate existing inbox to new structure
INSERT INTO auth.inbox_members (inbox_id, user_id, role, is_default)
SELECT i.id, 'fc6df517-8ea6-4d53-a78c-519566b2a71a', 'owner', true
FROM auth.inboxes i
WHERE NOT EXISTS (
  SELECT 1 FROM auth.inbox_members im WHERE im.inbox_id = i.id
);
