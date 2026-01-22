"""Obsidian sync worker tasks."""
import json
from datetime import date, datetime
from substrate.core.worker.registry import register_task
from substrate.core.db.connection import get_connection
from .sync import iter_vault_files
from substrate.domains.notes.embeddings import update_all_embeddings, update_note_embedding, update_note_chunks


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


@register_task("obsidian.index")
def index_vault(ctx, vault_path: str = None, embed: bool = True):
    """Index all files from Obsidian vault into notes domain."""
    indexed = 0
    changed_ids = []

    with get_connection() as conn:
        for note in iter_vault_files(vault_path):
            result = conn.execute("""
                INSERT INTO notes.notes (file_path, file_hash, frontmatter, title, tags, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE SET
                    file_hash = EXCLUDED.file_hash,
                    frontmatter = EXCLUDED.frontmatter,
                    title = EXCLUDED.title,
                    tags = EXCLUDED.tags,
                    content = EXCLUDED.content,
                    updated_at = now()
                WHERE notes.notes.file_hash != EXCLUDED.file_hash
                RETURNING id
            """, (
                note["file_path"],
                note["file_hash"],
                json.dumps(note["frontmatter"], cls=DateEncoder),
                note["title"],
                note["tags"],
                note["content"],
            ))
            row = result.fetchone()
            if row:
                changed_ids.append(str(row['id']))
            indexed += 1
        conn.commit()

        # Embed and chunk only changed notes
        embedded = 0
        chunked = 0
        if embed and changed_ids:
            for note_id in changed_ids:
                try:
                    if update_note_embedding(note_id, conn):
                        embedded += 1
                    chunk_count = update_note_chunks(note_id, conn)
                    if chunk_count > 0:
                        chunked += 1
                except Exception as e:
                    print(f"Failed to embed/chunk {note_id}: {e}")

    return {"indexed": indexed, "changed": len(changed_ids), "embedded": embedded, "chunked": chunked}


def sync_vault(vault_path: str = None, embed: bool = True) -> dict:
    """Sync vault directly (without worker). Useful for CLI/testing."""
    indexed = 0
    changed_ids = []

    with get_connection() as conn:
        for note in iter_vault_files(vault_path):
            # Use RETURNING to get ID of changed notes
            result = conn.execute("""
                INSERT INTO notes.notes (file_path, file_hash, frontmatter, title, tags, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE SET
                    file_hash = EXCLUDED.file_hash,
                    frontmatter = EXCLUDED.frontmatter,
                    title = EXCLUDED.title,
                    tags = EXCLUDED.tags,
                    content = EXCLUDED.content,
                    updated_at = now()
                WHERE notes.notes.file_hash != EXCLUDED.file_hash
                RETURNING id
            """, (
                note["file_path"],
                note["file_hash"],
                json.dumps(note["frontmatter"], cls=DateEncoder),
                note["title"],
                note["tags"],
                note["content"],
            ))
            row = result.fetchone()
            if row:
                changed_ids.append(str(row['id']))
            indexed += 1
        conn.commit()

        # Generate embeddings and chunks only for changed notes
        embedded = 0
        chunked = 0
        if embed and changed_ids:
            for note_id in changed_ids:
                try:
                    if update_note_embedding(note_id, conn):
                        embedded += 1
                    chunk_count = update_note_chunks(note_id, conn)
                    if chunk_count > 0:
                        chunked += 1
                except Exception as e:
                    print(f"Failed to embed/chunk {note_id}: {e}")

    return {"indexed": indexed, "changed": len(changed_ids), "embedded": embedded, "chunked": chunked}


def _do_sync(vault_path: str = None, embed: bool = True) -> dict:
    """Internal sync function for scheduler (wraps sync_vault)."""
    return sync_vault(vault_path, embed)


@register_task("obsidian.embed")
def update_embeddings(ctx, batch_size: int = 50):
    """Update embeddings for notes that need them."""
    stats = update_all_embeddings(batch_size=batch_size)
    return stats
