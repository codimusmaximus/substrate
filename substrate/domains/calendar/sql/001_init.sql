-- Calendar domain schema
CREATE SCHEMA IF NOT EXISTS calendar;

-- Events: meetings, calls, appointments, focus blocks
CREATE TABLE calendar.events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event details
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,                     -- physical address or video link

    -- Type & status
    type TEXT DEFAULT 'meeting',       -- meeting, call, reminder, focus, appointment
    status TEXT DEFAULT 'confirmed',   -- tentative, confirmed, cancelled

    -- Timing
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    all_day BOOLEAN DEFAULT FALSE,

    -- Links (polymorphic, all optional)
    contact_id UUID,                   -- primary contact (crm.contacts)
    company_id UUID,                   -- related company (crm.companies)

    -- Reminders
    remind_before_minutes INT,         -- e.g., 15, 60, 1440 (1 day)
    reminder_sent BOOLEAN DEFAULT FALSE,

    -- Flexible data
    tags TEXT[] DEFAULT '{}',
    data JSONB DEFAULT '{}',           -- video_link, notes, outcomes, etc.

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Event attendees
CREATE TABLE calendar.attendees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES calendar.events(id) ON DELETE CASCADE,

    -- Link to CRM (optional - external attendees may not have a contact record)
    contact_id UUID,

    -- Attendee info
    email TEXT NOT NULL,
    name TEXT,

    -- Response tracking
    status TEXT DEFAULT 'pending',     -- pending, accepted, declined, tentative
    is_organizer BOOLEAN DEFAULT FALSE,
    is_optional BOOLEAN DEFAULT FALSE,

    -- Invite tracking
    invite_sent BOOLEAN DEFAULT FALSE,
    invite_sent_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(event_id, email)
);

-- Indexes for events
CREATE INDEX events_starts_at_idx ON calendar.events (starts_at);
CREATE INDEX events_ends_at_idx ON calendar.events (ends_at);
CREATE INDEX events_type_idx ON calendar.events (type);
CREATE INDEX events_status_idx ON calendar.events (status);
CREATE INDEX events_contact_idx ON calendar.events (contact_id);
CREATE INDEX events_company_idx ON calendar.events (company_id);
CREATE INDEX events_tags_idx ON calendar.events USING GIN (tags);

-- Index for reminder queries
CREATE INDEX events_reminder_pending_idx ON calendar.events (starts_at, remind_before_minutes)
    WHERE remind_before_minutes IS NOT NULL AND NOT reminder_sent AND status = 'confirmed';

-- Indexes for attendees
CREATE INDEX attendees_event_idx ON calendar.attendees (event_id);
CREATE INDEX attendees_contact_idx ON calendar.attendees (contact_id);
CREATE INDEX attendees_email_idx ON calendar.attendees (email);
CREATE INDEX attendees_status_idx ON calendar.attendees (status);

-- Upcoming events view
CREATE VIEW calendar.upcoming AS
SELECT * FROM calendar.events
WHERE status != 'cancelled'
  AND ends_at >= now()
ORDER BY starts_at;

-- Today's events view
CREATE VIEW calendar.today AS
SELECT * FROM calendar.events
WHERE status != 'cancelled'
  AND starts_at::date = CURRENT_DATE
ORDER BY starts_at;

-- Events needing reminders view
CREATE VIEW calendar.needs_reminder AS
SELECT * FROM calendar.events
WHERE status = 'confirmed'
  AND NOT reminder_sent
  AND remind_before_minutes IS NOT NULL
  AND starts_at - (remind_before_minutes || ' minutes')::interval <= now()
  AND starts_at > now();
