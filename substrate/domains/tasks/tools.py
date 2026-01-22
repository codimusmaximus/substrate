"""AI tools for tasks domain."""
from datetime import datetime
from typing import Any

from psycopg.types.json import Json
from substrate.core.db.connection import get_connection


def list_pending_tasks(
    priority: str = None,
    contact_id: str = None,
    company_id: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    List pending tasks (not done/cancelled).

    Args:
        priority: Filter by priority (low, medium, high, urgent)
        contact_id: Filter by linked contact
        company_id: Filter by linked company
        limit: Max results

    Returns:
        List of pending tasks ordered by priority and due date
    """
    conditions = ["status IN ('pending', 'in_progress')"]
    params = []

    if priority:
        conditions.append("priority = %s")
        params.append(priority)
    if contact_id:
        conditions.append("contact_id = %s")
        params.append(contact_id)
    if company_id:
        conditions.append("company_id = %s")
        params.append(company_id)

    where = " AND ".join(conditions)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, title, status, priority, due_at, contact_id, company_id, tags, created_at
            FROM tasks.tasks
            WHERE {where}
            ORDER BY
                CASE priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                due_at NULLS LAST
            LIMIT %s
        """, params).fetchall()

    return [dict(r) for r in rows]


def query_tasks(
    status: str = None,
    priority: str = None,
    search: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search all tasks by status, priority, or title.

    Args:
        status: Filter by status (pending, in_progress, done, cancelled)
        priority: Filter by priority
        search: Search in title
        limit: Max results
    """
    conditions = []
    params = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if priority:
        conditions.append("priority = %s")
        params.append(priority)
    if search:
        conditions.append("title ILIKE %s")
        params.append(f"%{search}%")

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, title, status, priority, due_at, contact_id, company_id, created_at
            FROM tasks.tasks
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s
        """, params).fetchall()

    return [dict(r) for r in rows]


def get_task(task_id: str) -> dict | None:
    """Get full task details by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tasks.tasks WHERE id = %s",
            (task_id,)
        ).fetchone()
    return dict(row) if row else None


def create_task(
    title: str,
    description: str = None,
    priority: str = "medium",
    due_at: str = None,
    contact_id: str = None,
    company_id: str = None,
    event_id: str = None,
    note_id: str = None,
    assigned_to: str = None,
    tags: list = None,
    data: dict = None,
) -> dict:
    """
    Create a new task.

    Args:
        title: Task title (required)
        description: Task details
        priority: low, medium, high, urgent
        due_at: Due date (ISO format)
        contact_id: Link to CRM contact
        company_id: Link to CRM company
        event_id: Link to event
        note_id: Link to note
        assigned_to: Who should do this
        tags: List of tags
        data: Custom fields

    Returns:
        Created task
    """
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO tasks.tasks
            (title, description, priority, due_at, contact_id, company_id, event_id, note_id, assigned_to, tags, data)
            VALUES (%s, %s, %s, %s::timestamptz, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            title, description, priority, due_at,
            contact_id, company_id, event_id, note_id,
            assigned_to, tags or [], Json(data or {})
        )).fetchone()
        conn.commit()
    return dict(row)


def update_task(task_id: str, **kwargs) -> dict | None:
    """
    Update a task.

    Args:
        task_id: UUID of task
        **kwargs: Fields to update

    Returns:
        Updated task
    """
    allowed = ['title', 'description', 'status', 'priority', 'due_at', 'reminder_at',
               'contact_id', 'company_id', 'event_id', 'note_id', 'assigned_to', 'tags', 'data']
    updates = []
    params = []

    for key, value in kwargs.items():
        if key in allowed and value is not None:
            if key in ['due_at', 'reminder_at']:
                updates.append(f"{key} = %s::timestamptz")
            else:
                updates.append(f"{key} = %s")

            if key == 'data':
                params.append(Json(value))
            else:
                params.append(value)

    if not updates:
        return get_task(task_id)

    updates.append("updated_at = %s")
    params.append(datetime.utcnow())
    params.append(task_id)

    with get_connection() as conn:
        row = conn.execute(f"""
            UPDATE tasks.tasks
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING *
        """, params).fetchone()
        conn.commit()

    return dict(row) if row else None


def complete_task(task_id: str) -> dict | None:
    """
    Mark a task as done.

    Args:
        task_id: UUID of task

    Returns:
        Updated task
    """
    with get_connection() as conn:
        row = conn.execute("""
            UPDATE tasks.tasks
            SET status = 'done', completed_at = %s, updated_at = %s
            WHERE id = %s
            RETURNING *
        """, (datetime.utcnow(), datetime.utcnow(), task_id)).fetchone()
        conn.commit()
    return dict(row) if row else None


def cancel_task(task_id: str) -> dict | None:
    """
    Cancel a task.

    Args:
        task_id: UUID of task

    Returns:
        Updated task
    """
    with get_connection() as conn:
        row = conn.execute("""
            UPDATE tasks.tasks
            SET status = 'cancelled', updated_at = %s
            WHERE id = %s
            RETURNING *
        """, (datetime.utcnow(), task_id)).fetchone()
        conn.commit()
    return dict(row) if row else None


# Export tools for AI discovery
TOOLS = [
    list_pending_tasks,
    query_tasks,
    get_task,
    create_task,
    update_task,
    complete_task,
    cancel_task,
]
