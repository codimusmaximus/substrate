-- Add pgvector embeddings for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column (1536 dimensions for OpenAI text-embedding-3-small)
ALTER TABLE notes.notes ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS notes_embedding_idx ON notes.notes
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Track when embedding was last generated
ALTER TABLE notes.notes ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMPTZ;
