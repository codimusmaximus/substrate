"""Embedding generation and semantic search for notes."""

import os
import re
import time
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from openai import OpenAI, RateLimitError, APIError

from substrate.core.config import DATABASE_URL

# Model for embeddings (1536 dimensions)
EMBEDDING_MODEL = "text-embedding-3-small"

# Lazy-loaded OpenAI client
_client = None


def get_client() -> OpenAI:
    """Get OpenAI client, initializing lazily."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=api_key)
    return _client

# Chunk settings
CHUNK_SIZE = 500  # target chars per chunk
CHUNK_OVERLAP = 50  # overlap between chunks

# Rate limiting
MAX_RETRIES = 5
BASE_DELAY = 1.0  # seconds
REQUEST_DELAY = 0.05  # 50ms between requests


def generate_embedding(text: str, retries: int = MAX_RETRIES) -> list[float]:
    """Generate embedding vector for text using OpenAI with exponential backoff."""
    if not text or not text.strip():
        return None

    # Truncate to ~8000 tokens worth of text (roughly 32000 chars)
    text = text[:32000]

    for attempt in range(retries):
        try:
            # Small delay between requests to avoid hitting rate limits
            if attempt == 0:
                time.sleep(REQUEST_DELAY)

            response = get_client().embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            return response.data[0].embedding

        except RateLimitError as e:
            delay = BASE_DELAY * (2 ** attempt)
            print(f"Rate limited, waiting {delay:.1f}s (attempt {attempt + 1}/{retries})")
            time.sleep(delay)

        except APIError as e:
            if attempt < retries - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"API error: {e}, retrying in {delay:.1f}s")
                time.sleep(delay)
            else:
                raise

    return None


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, respecting paragraph boundaries."""
    if not text or not text.strip():
        return []

    # Split by double newlines (paragraphs) or headers
    segments = re.split(r'\n\n+|\n(?=#)', text)
    segments = [s.strip() for s in segments if s.strip()]

    chunks = []
    current_chunk = ""

    for segment in segments:
        # If adding this segment exceeds chunk size, save current and start new
        if current_chunk and len(current_chunk) + len(segment) > chunk_size:
            chunks.append(current_chunk.strip())
            # Start new chunk with overlap from end of previous
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + "\n\n" + segment
            else:
                current_chunk = segment
        else:
            if current_chunk:
                current_chunk += "\n\n" + segment
            else:
                current_chunk = segment

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def prepare_note_text(note: dict) -> str:
    """Prepare note content for embedding."""
    parts = []

    # Add title
    if note.get("title"):
        parts.append(f"# {note['title']}")

    # Add tags
    if note.get("tags"):
        tags = " ".join(note["tags"]) if isinstance(note["tags"], list) else note["tags"]
        parts.append(f"Tags: {tags}")

    # Add frontmatter context
    if note.get("frontmatter"):
        fm = note["frontmatter"]
        if fm.get("type"):
            parts.append(f"Type: {fm['type']}")
        if fm.get("status"):
            parts.append(f"Status: {fm['status']}")
        if fm.get("area"):
            parts.append(f"Area: {fm['area']}")

    # Add content
    if note.get("content"):
        parts.append(note["content"])

    return "\n\n".join(parts)


def update_note_embedding(note_id: str, conn: Optional[psycopg.Connection] = None) -> bool:
    """Generate and store embedding for a note."""
    should_close = False
    if conn is None:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        should_close = True

    try:
        # Fetch note
        row = conn.execute(
            "SELECT id, title, content, tags, frontmatter FROM notes.notes WHERE id = %s",
            (note_id,)
        ).fetchone()

        if not row:
            return False

        note = {
            "id": str(row["id"]),
            "title": row["title"],
            "content": row["content"],
            "tags": row["tags"],
            "frontmatter": row["frontmatter"],
        }

        # Generate embedding
        text = prepare_note_text(note)
        embedding = generate_embedding(text)

        if embedding:
            # Store embedding
            conn.execute(
                """
                UPDATE notes.notes
                SET embedding = %s::vector, embedding_updated_at = now()
                WHERE id = %s
                """,
                (embedding, note_id)
            )
            conn.commit()
            return True

        return False
    finally:
        if should_close:
            conn.close()


def update_all_embeddings(batch_size: int = 50) -> dict:
    """Update embeddings for all notes that need it."""
    stats = {"updated": 0, "failed": 0, "skipped": 0}

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        # Get notes without embeddings or with stale embeddings
        rows = conn.execute("""
            SELECT id, title, content, tags, frontmatter
            FROM notes.notes
            WHERE embedding IS NULL
               OR embedding_updated_at IS NULL
               OR embedding_updated_at < updated_at
            LIMIT %s
        """, (batch_size,)).fetchall()

        for row in rows:
            note = {
                "id": str(row["id"]),
                "title": row["title"],
                "content": row["content"],
                "tags": row["tags"],
                "frontmatter": row["frontmatter"],
            }

            text = prepare_note_text(note)
            if not text.strip():
                stats["skipped"] += 1
                continue

            try:
                embedding = generate_embedding(text)
                if embedding:
                    conn.execute(
                        """
                        UPDATE notes.notes
                        SET embedding = %s::vector, embedding_updated_at = now()
                        WHERE id = %s
                        """,
                        (embedding, note["id"])
                    )
                    conn.commit()
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                print(f"Failed to embed note {note['id']}: {e}")
                stats["failed"] += 1

    return stats


def semantic_search(query: str, limit: int = 10, threshold: float = 0.3) -> list[dict]:
    """Search notes by semantic similarity (whole document)."""
    # Generate query embedding
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        # Search by cosine similarity
        rows = conn.execute("""
            SELECT
                id, title, file_path, tags, frontmatter,
                substring(content, 1, 300) as content_preview,
                1 - (embedding <=> %s::vector) as similarity
            FROM notes.notes
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, limit)).fetchall()

        results = []
        for row in rows:
            similarity = row["similarity"]
            if similarity < threshold:
                continue
            results.append({
                "id": str(row["id"]),
                "title": row["title"],
                "file_path": row["file_path"],
                "tags": row["tags"],
                "frontmatter": row["frontmatter"],
                "content_preview": row["content_preview"],
                "similarity": round(similarity, 3),
            })

        return results


def update_note_chunks(note_id: str, conn: Optional[psycopg.Connection] = None) -> int:
    """Generate and store chunks with embeddings for a note."""
    should_close = False
    if conn is None:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        should_close = True

    try:
        # Fetch note
        row = conn.execute(
            "SELECT id, title, content FROM notes.notes WHERE id = %s",
            (note_id,)
        ).fetchone()

        if not row:
            return 0

        note_id = str(row["id"])
        title = row["title"] or ""
        content = row["content"] or ""

        # Prepare full text and chunk it
        full_text = f"# {title}\n\n{content}" if title else content
        chunks = chunk_text(full_text)

        if not chunks:
            return 0

        # Delete existing chunks for this note
        conn.execute("DELETE FROM notes.chunks WHERE note_id = %s", (note_id,))

        # Insert new chunks with embeddings
        count = 0
        for i, chunk_content in enumerate(chunks):
            embedding = generate_embedding(chunk_content)
            if embedding:
                conn.execute("""
                    INSERT INTO notes.chunks (note_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                """, (note_id, i, chunk_content, embedding))
                count += 1

        conn.commit()
        return count
    finally:
        if should_close:
            conn.close()


def update_all_chunks(batch_size: int = 20) -> dict:
    """Update chunks for notes that need them."""
    stats = {"notes": 0, "chunks": 0, "failed": 0}

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        # Get notes without chunks or with stale chunks
        rows = conn.execute("""
            SELECT n.id, n.title
            FROM notes.notes n
            LEFT JOIN (
                SELECT note_id, MAX(created_at) as last_chunk
                FROM notes.chunks
                GROUP BY note_id
            ) c ON c.note_id = n.id
            WHERE c.note_id IS NULL
               OR c.last_chunk < n.updated_at
            LIMIT %s
        """, (batch_size,)).fetchall()

        for row in rows:
            note_id = str(row["id"])
            try:
                chunk_count = update_note_chunks(note_id, conn)
                if chunk_count > 0:
                    stats["notes"] += 1
                    stats["chunks"] += chunk_count
            except Exception as e:
                print(f"Failed to chunk note {note_id}: {e}")
                stats["failed"] += 1

    return stats


def search_chunks(query: str, limit: int = 10, threshold: float = 0.25) -> list[dict]:
    """Search note chunks by semantic similarity. Returns matching passages with context."""
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute("""
            SELECT
                c.id as chunk_id,
                c.note_id,
                c.chunk_index,
                c.content as chunk_content,
                n.title,
                n.file_path,
                n.tags,
                1 - (c.embedding <=> %s::vector) as similarity
            FROM notes.chunks c
            JOIN notes.notes n ON n.id = c.note_id
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, limit)).fetchall()

        results = []
        for row in rows:
            similarity = row["similarity"]
            if similarity < threshold:
                continue
            results.append({
                "chunk_id": str(row["chunk_id"]),
                "note_id": str(row["note_id"]),
                "chunk_index": row["chunk_index"],
                "chunk_content": row["chunk_content"],
                "title": row["title"],
                "file_path": row["file_path"],
                "tags": row["tags"],
                "similarity": round(similarity, 3),
            })

        return results


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "update":
        print("Updating note embeddings...")
        stats = update_all_embeddings(batch_size=100)
        print(f"Done: {stats}")

    elif cmd == "chunks":
        print("Updating chunks...")
        total = {"notes": 0, "chunks": 0, "failed": 0}
        while True:
            stats = update_all_chunks(batch_size=10)
            for k in total:
                total[k] += stats[k]
            print(f"Batch: {stats}")
            if stats["notes"] == 0:
                break
        print(f"Total: {total}")

    elif cmd == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "meeting notes"
        print(f"Searching notes for: {query}")
        results = semantic_search(query)
        for r in results:
            print(f"  [{r['similarity']}] {r['title']}")

    elif cmd == "search-chunks":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "meeting notes"
        print(f"Searching chunks for: {query}")
        results = search_chunks(query)
        for r in results:
            print(f"  [{r['similarity']}] {r['title']} (chunk {r['chunk_index']})")
            print(f"    {r['chunk_content'][:100]}...")

    else:
        print("Usage: python -m substrate.domains.notes.embeddings <command>")
        print("Commands:")
        print("  update         - Update note-level embeddings")
        print("  chunks         - Generate chunks with embeddings")
        print("  search <q>     - Search notes (whole document)")
        print("  search-chunks <q> - Search chunks (passages)")
