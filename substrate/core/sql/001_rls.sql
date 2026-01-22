-- Row Level Security for all domain tables
-- Private by default, with optional public sharing

-- Create app schema first
CREATE SCHEMA IF NOT EXISTS app;

-- Create app role (non-superuser) for application connections
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'substrate_app') THEN
    CREATE ROLE substrate_app WITH LOGIN PASSWORD 'substrate_app';
  END IF;
END
$$;

-- Helper: Get current user ID from session (set via SET app.user_id = '...')
-- Returns NULL if not set (allows superuser/migration access)
CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid AS $$
BEGIN
  RETURN NULLIF(current_setting('app.user_id', true), '')::uuid;
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================
-- NOTES
-- ============================================================
ALTER TABLE notes.notes ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE notes.notes ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT false;

ALTER TABLE notes.notes ENABLE ROW LEVEL SECURITY;

-- Policy: see own rows OR public rows OR all if no user set (admin/migration)
DROP POLICY IF EXISTS notes_isolation ON notes.notes;
CREATE POLICY notes_isolation ON notes.notes
  USING (
    app.current_user_id() IS NULL  -- No user set = admin access
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

-- Policy: can only insert/update own rows
DROP POLICY IF EXISTS notes_write ON notes.notes;
CREATE POLICY notes_write ON notes.notes
  FOR INSERT
  WITH CHECK (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
  );

DROP POLICY IF EXISTS notes_update ON notes.notes;
CREATE POLICY notes_update ON notes.notes
  FOR UPDATE
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
  );

-- ============================================================
-- NOTES CHUNKS (inherits from parent note)
-- ============================================================
ALTER TABLE notes.chunks ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE notes.chunks ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT false;

ALTER TABLE notes.chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chunks_isolation ON notes.chunks;
CREATE POLICY chunks_isolation ON notes.chunks
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

-- ============================================================
-- CRM CONTACTS
-- ============================================================
ALTER TABLE crm.contacts ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE crm.contacts ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT false;

ALTER TABLE crm.contacts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS contacts_isolation ON crm.contacts;
CREATE POLICY contacts_isolation ON crm.contacts
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

DROP POLICY IF EXISTS contacts_write ON crm.contacts;
CREATE POLICY contacts_write ON crm.contacts
  FOR INSERT
  WITH CHECK (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
  );

-- ============================================================
-- CRM COMPANIES
-- ============================================================
ALTER TABLE crm.companies ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE crm.companies ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT false;

ALTER TABLE crm.companies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS companies_isolation ON crm.companies;
CREATE POLICY companies_isolation ON crm.companies
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

-- ============================================================
-- CRM INTERACTIONS
-- ============================================================
ALTER TABLE crm.interactions ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE crm.interactions ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT false;

ALTER TABLE crm.interactions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS interactions_isolation ON crm.interactions;
CREATE POLICY interactions_isolation ON crm.interactions
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

-- ============================================================
-- TASKS
-- ============================================================
ALTER TABLE tasks.tasks ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE tasks.tasks ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT false;

ALTER TABLE tasks.tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tasks_isolation ON tasks.tasks;
CREATE POLICY tasks_isolation ON tasks.tasks
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

DROP POLICY IF EXISTS tasks_write ON tasks.tasks;
CREATE POLICY tasks_write ON tasks.tasks
  FOR INSERT
  WITH CHECK (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
  );

-- ============================================================
-- EVENTS
-- ============================================================
ALTER TABLE events.events ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE events.events ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT false;

ALTER TABLE events.events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS events_isolation ON events.events;
CREATE POLICY events_isolation ON events.events
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

-- ============================================================
-- EVENT RULES (usually shared/system-wide, default public)
-- ============================================================
ALTER TABLE events.rules ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE events.rules ADD COLUMN IF NOT EXISTS is_public boolean DEFAULT true;  -- Rules default public

ALTER TABLE events.rules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rules_isolation ON events.rules;
CREATE POLICY rules_isolation ON events.rules
  USING (
    app.current_user_id() IS NULL
    OR owner_id = app.current_user_id()
    OR is_public = true
  );

-- ============================================================
-- INDEX for performance
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_notes_owner ON notes.notes(owner_id);
CREATE INDEX IF NOT EXISTS idx_chunks_owner ON notes.chunks(owner_id);
CREATE INDEX IF NOT EXISTS idx_contacts_owner ON crm.contacts(owner_id);
CREATE INDEX IF NOT EXISTS idx_companies_owner ON crm.companies(owner_id);
CREATE INDEX IF NOT EXISTS idx_interactions_owner ON crm.interactions(owner_id);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks.tasks(owner_id);
CREATE INDEX IF NOT EXISTS idx_events_owner ON events.events(owner_id);
CREATE INDEX IF NOT EXISTS idx_rules_owner ON events.rules(owner_id);

-- ============================================================
-- FORCE RLS (even for table owner, but not superuser)
-- ============================================================
ALTER TABLE notes.notes FORCE ROW LEVEL SECURITY;
ALTER TABLE notes.chunks FORCE ROW LEVEL SECURITY;
ALTER TABLE crm.contacts FORCE ROW LEVEL SECURITY;
ALTER TABLE crm.companies FORCE ROW LEVEL SECURITY;
ALTER TABLE crm.interactions FORCE ROW LEVEL SECURITY;
ALTER TABLE tasks.tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE events.events FORCE ROW LEVEL SECURITY;
ALTER TABLE events.rules FORCE ROW LEVEL SECURITY;

-- ============================================================
-- GRANTS for substrate_app role
-- ============================================================
GRANT USAGE ON SCHEMA notes, crm, tasks, events, app TO substrate_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA notes TO substrate_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA crm TO substrate_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tasks TO substrate_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA events TO substrate_app;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA notes TO substrate_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA crm TO substrate_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA tasks TO substrate_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA events TO substrate_app;

GRANT EXECUTE ON FUNCTION app.current_user_id() TO substrate_app;
