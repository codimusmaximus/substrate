"""AI tools for notes domain with two-way sync."""
import json
from substrate.core.db.connection import get_connection
from substrate.integrations.obsidian.writeback import write_note_to_file, note_to_markdown
from substrate.integrations.obsidian.git import git_commit_and_push


def query_notes(query: str = None, tag: str = None, limit: int = 10) -> list[dict]:
    """Search notes by keyword or tag.

    Args:
        query: Text to search in title/content
        tag: Tag to filter by (e.g., "#work")
        limit: Max results to return
    """
    with get_connection() as conn:
        if tag:
            rows = conn.execute(
                "SELECT id, title, tags, file_path FROM notes.notes WHERE %s = ANY(tags) LIMIT %s",
                (tag, limit)
            ).fetchall()
        elif query:
            rows = conn.execute(
                "SELECT id, title, tags, file_path FROM notes.notes WHERE title ILIKE %s OR content ILIKE %s LIMIT %s",
                (f"%{query}%", f"%{query}%", limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, tags, file_path FROM notes.notes ORDER BY updated_at DESC LIMIT %s",
                (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_note(note_id: str) -> dict:
    """Get full note by ID.

    Args:
        note_id: UUID of the note
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notes.notes WHERE id = %s", (note_id,)
        ).fetchone()
    return dict(row) if row else None


def create_note(
    title: str,
    content: str,
    tags: list[str] = None,
    frontmatter: dict = None,
    folder: str = "notes"
) -> dict:
    """Create a new note in both database and vault.

    Args:
        title: Note title
        content: Markdown content
        tags: List of tags (e.g., ["#work", "#ideas"])
        frontmatter: YAML frontmatter dict (e.g., {"status": "draft", "type": "note"})
        folder: Folder in vault (default: "notes")
    """
    # Generate file path
    slug = title.lower().replace(" ", "-").replace("/", "-")
    for char in ["'", '"', "?", "!", ":", ";", "(", ")", "[", "]", "{", "}"]:
        slug = slug.replace(char, "")
    file_path = f"{folder}/{slug}.md"

    # Merge tags into frontmatter
    fm = frontmatter or {}
    if tags:
        fm["tags"] = [t.lstrip("#") for t in tags]

    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO notes.notes (file_path, title, content, frontmatter, tags)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (file_path, title, content, json.dumps(fm), tags or [])).fetchone()
        conn.commit()

    note = dict(row)

    # Write to vault file
    write_note_to_file(note)

    # Commit and push
    git_result = git_commit_and_push(f"Add: {title}")

    return {
        "id": str(note["id"]),
        "title": note["title"],
        "file_path": note["file_path"],
        "synced": git_result.get("success", False)
    }


def update_note(
    note_id: str,
    title: str = None,
    content: str = None,
    tags: list[str] = None,
    frontmatter: dict = None
) -> dict:
    """Update an existing note in both database and vault.

    Args:
        note_id: UUID of the note to update
        title: New title (optional)
        content: New content (optional)
        tags: New tags (optional)
        frontmatter: New frontmatter to merge (optional)
    """
    with get_connection() as conn:
        # Get current note
        row = conn.execute(
            "SELECT * FROM notes.notes WHERE id = %s", (note_id,)
        ).fetchone()

        if not row:
            return {"error": "Note not found"}

        current = dict(row)

        # Build update
        updates = []
        params = []

        if title is not None:
            updates.append("title = %s")
            params.append(title)

        if content is not None:
            updates.append("content = %s")
            params.append(content)

        if tags is not None:
            updates.append("tags = %s")
            params.append(tags)

        if frontmatter is not None:
            # Merge with existing frontmatter
            current_fm = current.get("frontmatter") or {}
            merged_fm = {**current_fm, **frontmatter}
            updates.append("frontmatter = %s")
            params.append(json.dumps(merged_fm))

        if not updates:
            return {"error": "No updates provided"}

        updates.append("updated_at = now()")
        params.append(note_id)

        query = f"UPDATE notes.notes SET {', '.join(updates)} WHERE id = %s RETURNING *"
        row = conn.execute(query, params).fetchone()
        conn.commit()

    note = dict(row)

    # Write to vault file
    write_note_to_file(note)

    # Commit and push
    git_result = git_commit_and_push(f"Update: {note['title']}")

    return {
        "id": str(note["id"]),
        "title": note["title"],
        "file_path": note["file_path"],
        "synced": git_result.get("success", False)
    }


def delete_note(note_id: str) -> dict:
    """Delete a note from database. File remains in vault (manual cleanup).

    Args:
        note_id: UUID of the note to delete
    """
    with get_connection() as conn:
        row = conn.execute(
            "DELETE FROM notes.notes WHERE id = %s RETURNING title, file_path",
            (note_id,)
        ).fetchone()
        conn.commit()

    if not row:
        return {"error": "Note not found"}

    return {"deleted": True, "title": row[0], "file_path": row[1]}


# Export tools for discovery
TOOLS = [query_notes, get_note, create_note, update_note, delete_note]
