"""Write notes from DB back to Obsidian vault files."""
import os
import yaml
from pathlib import Path
from substrate.core.config import VAULT_PATH
from substrate.core.db.connection import get_connection


def note_to_markdown(note: dict) -> str:
    """Convert a note dict to markdown with frontmatter."""
    parts = []

    # Add frontmatter if present
    frontmatter = note.get("frontmatter", {})
    if frontmatter:
        parts.append("---")
        parts.append(yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True).strip())
        parts.append("---")
        parts.append("")

    # Add content
    content = note.get("content", "")
    parts.append(content)

    return "\n".join(parts)


def write_note_to_file(note: dict, vault_path: str = None) -> dict:
    """Write a single note to the vault as a markdown file."""
    vault = Path(vault_path or VAULT_PATH)

    file_path = note.get("file_path")
    if not file_path:
        # Generate file path from title
        title = note.get("title", "untitled")
        slug = title.lower().replace(" ", "-").replace("/", "-")
        file_path = f"notes/{slug}.md"

    full_path = vault / file_path

    # Ensure directory exists
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Write markdown
    markdown = note_to_markdown(note)
    full_path.write_text(markdown)

    return {"written": True, "path": str(file_path)}


def sync_note_to_vault(note_id: str, vault_path: str = None) -> dict:
    """Sync a specific note from DB to vault file."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notes.notes WHERE id = %s",
            (note_id,)
        ).fetchone()

    if not row:
        return {"error": "Note not found"}

    note = dict(row)
    return write_note_to_file(note, vault_path)


def sync_modified_to_vault(vault_path: str = None) -> dict:
    """Sync all notes modified in DB (newer than file) back to vault."""
    vault = Path(vault_path or VAULT_PATH)
    synced = []

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM notes.notes
            WHERE file_path IS NOT NULL
            ORDER BY updated_at DESC
        """).fetchall()

    for row in rows:
        note = dict(row)
        file_path = vault / note["file_path"]

        # Check if file needs update (DB is newer or file doesn't exist)
        if not file_path.exists():
            result = write_note_to_file(note, vault_path)
            synced.append(result["path"])
        else:
            # Compare modification times
            file_mtime = file_path.stat().st_mtime
            db_updated = note["updated_at"].timestamp() if note.get("updated_at") else 0

            if db_updated > file_mtime:
                result = write_note_to_file(note, vault_path)
                synced.append(result["path"])

    return {"synced": len(synced), "files": synced}
