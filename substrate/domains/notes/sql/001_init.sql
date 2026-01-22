-- Notes domain schema
CREATE SCHEMA IF NOT EXISTS notes;

CREATE TABLE notes.notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT UNIQUE,
    file_hash TEXT,
    title TEXT,
    content TEXT,
    frontmatter JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX notes_tags_idx ON notes.notes USING GIN (tags);
CREATE INDEX notes_frontmatter_idx ON notes.notes USING GIN (frontmatter);
