-- Chunk table for granular semantic search
CREATE TABLE IF NOT EXISTS notes.chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID NOT NULL REFERENCES notes.notes(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(note_id, chunk_index)
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON notes.chunks
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Index for looking up chunks by note
CREATE INDEX IF NOT EXISTS chunks_note_id_idx ON notes.chunks(note_id);
