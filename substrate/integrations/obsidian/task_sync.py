"""Sync tasks from vault's All Tasks.md to tasks.tasks table."""
import hashlib
import re
from pathlib import Path
from datetime import datetime

from substrate.core.config import VAULT_PATH
from substrate.core.db.connection import get_connection


# Map Eisenhower quadrants to priority
QUADRANT_TO_PRIORITY = {
    "#do": "urgent",        # Urgent + Important
    "#plan": "high",        # Important, not urgent
    "#delegate": "medium",  # Urgent, not important
    "#drop": "low",         # Neither
}


def parse_all_tasks_md(vault_path: str = None) -> list[dict]:
    """
    Parse Overview/All Tasks.md and extract tasks.

    Returns list of task dicts ready for DB insert.
    """
    vault = Path(vault_path or VAULT_PATH)
    tasks_file = vault / "Overview" / "All Tasks.md"

    if not tasks_file.exists():
        return []

    content = tasks_file.read_text()
    tasks = []

    # Find the "All Tasks" table section
    # Format: | Status | Task | Due | Quadrant | Assignee | Source |
    in_table = False
    for line in content.split("\n"):
        line = line.strip()

        # Detect table start
        if line.startswith("| Status |"):
            in_table = True
            continue

        # Skip separator line
        if in_table and line.startswith("|---"):
            continue

        # End of table
        if in_table and not line.startswith("|"):
            break

        # Parse table row
        if in_table and line.startswith("|"):
            task = parse_task_row(line)
            if task:
                tasks.append(task)

    return tasks


def parse_task_row(line: str) -> dict | None:
    """Parse a single task table row."""
    # Split by | and strip
    parts = [p.strip() for p in line.split("|")]
    # Remove empty first/last from | split
    parts = [p for p in parts if p]

    if len(parts) < 6:
        return None

    status_icon, title, due, quadrant, assignee, source = parts[:6]

    # Parse status
    is_done = status_icon == "✅"
    status = "done" if is_done else "pending"

    # Parse priority from quadrant
    quadrant = quadrant.strip()
    priority = QUADRANT_TO_PRIORITY.get(quadrant, "medium")

    # Parse assignee (remove @)
    assignee = assignee.strip()
    if assignee.startswith("@"):
        assignee = assignee[1:]
    assignee = assignee if assignee and assignee != "-" else None

    # Parse due date
    due = due.strip()
    due_at = None
    if due and due != "-":
        try:
            due_at = datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            pass

    # Parse source (extract from [[Note Name]])
    source = source.strip()
    source_match = re.search(r"\[\[([^\]]+)\]\]", source)
    source_note = source_match.group(1) if source_match else source

    # Generate stable ID from title + source
    task_hash = hashlib.md5(f"{title}:{source_note}".encode()).hexdigest()[:12]

    return {
        "external_id": f"vault:{task_hash}",
        "title": title,
        "status": status,
        "priority": priority,
        "assigned_to": assignee,
        "due_at": due_at,
        "quadrant": quadrant if quadrant != "-" else None,
        "source_note": source_note,
        "tags": [quadrant] if quadrant and quadrant != "-" else [],
    }


def sync_tasks(vault_path: str = None) -> dict:
    """
    Sync tasks from All Tasks.md to tasks.tasks table.

    Returns: {"synced": int, "created": int, "updated": int}
    """
    tasks = parse_all_tasks_md(vault_path)

    created = 0
    updated = 0

    with get_connection() as conn:
        for task in tasks:
            # Check if task exists (by external_id in data jsonb)
            existing = conn.execute("""
                SELECT id, status FROM tasks.tasks
                WHERE data->>'external_id' = %s
            """, (task["external_id"],)).fetchone()

            if existing:
                # Update existing task
                conn.execute("""
                    UPDATE tasks.tasks SET
                        title = %s,
                        status = %s,
                        priority = %s,
                        assigned_to = %s,
                        due_at = %s,
                        tags = %s,
                        data = data || %s::jsonb,
                        updated_at = now()
                    WHERE data->>'external_id' = %s
                """, (
                    task["title"],
                    task["status"],
                    task["priority"],
                    task["assigned_to"],
                    task["due_at"],
                    task["tags"],
                    f'{{"quadrant": "{task["quadrant"]}", "source_note": "{task["source_note"]}"}}',
                    task["external_id"],
                ))
                updated += 1
            else:
                # Create new task
                conn.execute("""
                    INSERT INTO tasks.tasks
                    (title, status, priority, assigned_to, due_at, tags, data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    task["title"],
                    task["status"],
                    task["priority"],
                    task["assigned_to"],
                    task["due_at"],
                    task["tags"],
                    f'{{"external_id": "{task["external_id"]}", "quadrant": "{task["quadrant"]}", "source_note": "{task["source_note"]}"}}',
                ))
                created += 1

        conn.commit()

    return {"synced": len(tasks), "created": created, "updated": updated}


if __name__ == "__main__":
    # CLI usage: python -m substrate.integrations.obsidian.task_sync
    import sys
    vault = sys.argv[1] if len(sys.argv) > 1 else None
    result = sync_tasks(vault)
    print(f"Synced {result['synced']} tasks: {result['created']} created, {result['updated']} updated")
