-- Events domain schema
CREATE SCHEMA IF NOT EXISTS events;

-- Incoming events (emails, webhooks, etc.)
CREATE TABLE events.events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,              -- 'email', 'webhook', 'manual'
    source_id TEXT,                    -- external ID (message_id for email)
    event_type TEXT NOT NULL,          -- 'email.received', 'webhook.received'
    status TEXT DEFAULT 'pending',     -- pending, processed, failed, ignored

    -- Event payload
    payload JSONB NOT NULL,            -- full event data

    -- Email-specific (denormalized for querying)
    email_from TEXT,
    email_to TEXT,
    email_subject TEXT,
    email_body TEXT,
    email_date TIMESTAMPTZ,

    -- Routing result
    matched_rule_id UUID,
    routed_at TIMESTAMPTZ,
    route_result JSONB,                -- {action: 'create_note', ...}

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(source, source_id)          -- prevent duplicate ingestion
);

-- Routing rules
CREATE TABLE events.rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT true,
    priority INT DEFAULT 0,            -- higher = checked first

    -- Matching conditions (JSONB for flexibility)
    conditions JSONB NOT NULL,         -- {from_contains: '@company.com', subject_contains: 'invoice'}

    -- Action to take
    action TEXT NOT NULL,              -- 'create_note', 'spawn_task', 'tag', 'ignore'
    action_config JSONB DEFAULT '{}',  -- action-specific params

    -- Stats
    match_count INT DEFAULT 0,
    last_matched_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Action log (audit trail)
CREATE TABLE events.actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events.events(id),
    rule_id UUID REFERENCES events.rules(id),

    action TEXT NOT NULL,              -- what was done
    action_input JSONB,                -- input to action
    action_output JSONB,               -- result of action
    status TEXT DEFAULT 'pending',     -- pending, completed, failed
    error TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX events_status_idx ON events.events (status);
CREATE INDEX events_source_idx ON events.events (source);
CREATE INDEX events_event_type_idx ON events.events (event_type);
CREATE INDEX events_email_from_idx ON events.events (email_from);
CREATE INDEX events_created_at_idx ON events.events (created_at DESC);

CREATE INDEX rules_enabled_priority_idx ON events.rules (enabled, priority DESC);

CREATE INDEX actions_event_id_idx ON events.actions (event_id);
CREATE INDEX actions_status_idx ON events.actions (status);
