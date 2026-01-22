-- Tasks domain schema
CREATE SCHEMA IF NOT EXISTS tasks;

-- Tasks: pending actions, follow-ups, to-dos
CREATE TABLE tasks.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Task details
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',     -- pending, in_progress, done, cancelled
    priority TEXT DEFAULT 'medium',    -- low, medium, high, urgent

    -- Timing
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    reminder_at TIMESTAMPTZ,

    -- Polymorphic links (all optional)
    contact_id UUID,                   -- link to crm.contacts
    company_id UUID,                   -- link to crm.companies
    event_id UUID,                     -- link to events.events
    note_id UUID,                      -- link to notes.notes

    -- Assignment
    assigned_to TEXT,                  -- who should do this

    -- Flexible data
    tags TEXT[] DEFAULT '{}',
    data JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX tasks_status_idx ON tasks.tasks (status);
CREATE INDEX tasks_priority_idx ON tasks.tasks (priority);
CREATE INDEX tasks_due_at_idx ON tasks.tasks (due_at);
CREATE INDEX tasks_contact_idx ON tasks.tasks (contact_id);
CREATE INDEX tasks_company_idx ON tasks.tasks (company_id);
CREATE INDEX tasks_event_idx ON tasks.tasks (event_id);
CREATE INDEX tasks_tags_idx ON tasks.tasks USING GIN (tags);

-- Pending tasks view (for quick access)
CREATE VIEW tasks.pending AS
SELECT * FROM tasks.tasks
WHERE status IN ('pending', 'in_progress')
ORDER BY
    CASE priority
        WHEN 'urgent' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    due_at NULLS LAST,
    created_at;
