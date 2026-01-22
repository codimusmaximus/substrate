-- CRM domain schema
CREATE SCHEMA IF NOT EXISTS crm;

-- Contacts: people (leads, customers, investors, partners, etc.)
CREATE TABLE crm.contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic info
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,

    -- Classification
    type TEXT DEFAULT 'lead',          -- lead, customer, investor, partner, vendor, other
    status TEXT DEFAULT 'active',      -- active, inactive, churned, converted

    -- Organization
    company_id UUID,                   -- FK to companies (optional)
    title TEXT,                        -- job title

    -- Source tracking
    source TEXT,                       -- how we got this contact (referral, website, event, etc.)
    source_detail TEXT,                -- additional source info

    -- Flexible data
    tags TEXT[] DEFAULT '{}',
    data JSONB DEFAULT '{}',           -- custom fields, social links, etc.

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Companies: organizations
CREATE TABLE crm.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic info
    name TEXT NOT NULL,
    domain TEXT,                       -- website domain
    industry TEXT,
    size TEXT,                         -- startup, smb, enterprise

    -- Classification
    type TEXT DEFAULT 'prospect',      -- prospect, customer, partner, investor, vendor
    status TEXT DEFAULT 'active',

    -- Flexible data
    tags TEXT[] DEFAULT '{}',
    data JSONB DEFAULT '{}',           -- address, social, notes, etc.

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Add FK after companies table exists
ALTER TABLE crm.contacts
    ADD CONSTRAINT contacts_company_fk
    FOREIGN KEY (company_id) REFERENCES crm.companies(id);

-- Interactions: meetings, calls, emails, notes
CREATE TABLE crm.interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Links
    contact_id UUID REFERENCES crm.contacts(id),
    company_id UUID REFERENCES crm.companies(id),
    event_id UUID,                     -- optional link to events.events

    -- Interaction details
    type TEXT NOT NULL,                -- email, call, meeting, note, task
    direction TEXT,                    -- inbound, outbound (for emails/calls)
    subject TEXT,
    content TEXT,

    -- Timing
    occurred_at TIMESTAMPTZ DEFAULT now(),
    duration_minutes INT,

    -- Flexible data
    data JSONB DEFAULT '{}',           -- attendees, outcomes, follow-ups, etc.

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX contacts_email_idx ON crm.contacts (email);
CREATE INDEX contacts_type_idx ON crm.contacts (type);
CREATE INDEX contacts_status_idx ON crm.contacts (status);
CREATE INDEX contacts_company_idx ON crm.contacts (company_id);
CREATE INDEX contacts_tags_idx ON crm.contacts USING GIN (tags);

CREATE INDEX companies_domain_idx ON crm.companies (domain);
CREATE INDEX companies_type_idx ON crm.companies (type);
CREATE INDEX companies_tags_idx ON crm.companies USING GIN (tags);

CREATE INDEX interactions_contact_idx ON crm.interactions (contact_id);
CREATE INDEX interactions_company_idx ON crm.interactions (company_id);
CREATE INDEX interactions_type_idx ON crm.interactions (type);
CREATE INDEX interactions_occurred_idx ON crm.interactions (occurred_at DESC);
