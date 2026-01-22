"""Event actions - execute actions when rules match.

Supported actions:
- create_note: Create a note in the vault from event content
- tag: Add tags to the event for categorization
- ignore: Mark event as processed without action
- spawn_task: Queue a background task for processing
"""
from datetime import datetime
from typing import Any

from psycopg.types.json import Json
from substrate.core.db.connection import get_connection


def execute_action(
    event_id: str,
    rule_id: str,
    action: str,
    action_config: dict,
    event: dict,
) -> dict:
    """
    Execute an action for a matched event.

    Args:
        event_id: UUID of the event
        rule_id: UUID of the matched rule
        action: Action type to execute
        action_config: Action-specific configuration
        event: Full event dict

    Returns:
        Dict with success status and any output
    """
    # Create action log entry
    action_id = _log_action_start(event_id, rule_id, action, action_config)

    try:
        # Dispatch to action handler
        if action == "create_note":
            result = _action_create_note(event, action_config)
        elif action == "tag":
            result = _action_tag(event_id, action_config)
        elif action == "ignore":
            result = _action_ignore(event_id)
        elif action == "spawn_task":
            result = _action_spawn_task(event, action_config)
        else:
            result = {"success": False, "error": f"Unknown action: {action}"}

        # Update action log
        _log_action_complete(action_id, result)
        return result

    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        _log_action_complete(action_id, error_result, error=str(e))
        return error_result


def _log_action_start(event_id: str, rule_id: str, action: str, action_input: dict) -> str:
    """Create action log entry."""
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO events.actions (event_id, rule_id, action, action_input, status)
            VALUES (%s, %s, %s, %s, 'running')
            RETURNING id
        """, (event_id, rule_id, action, Json(action_input))).fetchone()
        conn.commit()
    return str(row["id"])


def _log_action_complete(action_id: str, result: dict, error: str = None):
    """Update action log with result."""
    status = "completed" if result.get("success") else "failed"
    with get_connection() as conn:
        conn.execute("""
            UPDATE events.actions
            SET status = %s, action_output = %s, error = %s, completed_at = %s
            WHERE id = %s
        """, (status, Json(result), error, datetime.utcnow(), action_id))
        conn.commit()


def _action_create_note(event: dict, config: dict) -> dict:
    """
    Create a note from event content.

    Config options:
    - folder: Where to create the note (default: 'Inbox')
    - title_template: Template for note title (default: email subject)
    - tags: Additional tags to add
    """
    from substrate.domains.notes.tools import create_note

    folder = config.get("folder", "Inbox")
    tags = config.get("tags", [])

    # Build note title
    title_template = config.get("title_template")
    if title_template:
        title = title_template.format(
            subject=event.get("email_subject", ""),
            from_=event.get("email_from", ""),
            date=event.get("email_date", ""),
        )
    else:
        title = event.get("email_subject") or "Untitled Event"

    # Build note content
    content = _format_event_as_note(event)

    # Create the note
    note = create_note(
        title=title,
        content=content,
        tags=tags,
        folder=folder,
        frontmatter={"source": "event", "event_id": str(event.get("id"))},
    )

    return {"success": True, "note_id": note.get("id"), "note_path": note.get("file_path")}


def _format_event_as_note(event: dict) -> str:
    """Format an event as markdown note content."""
    lines = []

    if event.get("source") == "email":
        lines.append(f"**From:** {event.get('email_from', 'Unknown')}")
        lines.append(f"**To:** {event.get('email_to', 'Unknown')}")
        lines.append(f"**Date:** {event.get('email_date', 'Unknown')}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(event.get("email_body", ""))
    else:
        lines.append(f"**Source:** {event.get('source')}")
        lines.append(f"**Type:** {event.get('event_type')}")
        lines.append("")
        lines.append("```json")
        import json
        lines.append(json.dumps(event.get("payload", {}), indent=2))
        lines.append("```")

    return "\n".join(lines)


def _action_tag(event_id: str, config: dict) -> dict:
    """
    Add tags to an event.

    Config options:
    - tags: List of tags to add
    """
    tags = config.get("tags", [])
    if not tags:
        return {"success": True, "message": "No tags specified"}

    # Store tags in route_result
    import json
    with get_connection() as conn:
        conn.execute("""
            UPDATE events.events
            SET route_result = COALESCE(route_result, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
        """, (json.dumps({"tags": tags}), event_id))
        conn.commit()

    return {"success": True, "tags_added": tags}


def _action_ignore(event_id: str) -> dict:
    """Mark event as ignored - no action needed."""
    return {"success": True, "message": "Event ignored"}


def _action_spawn_task(event: dict, config: dict) -> dict:
    """
    Spawn a background task to process the event.

    Config options:
    - task_name: Name of task to spawn
    - task_params: Additional params to pass to task
    """
    import json
    from uuid import UUID

    task_name = config.get("task_name")
    if not task_name:
        return {"success": False, "error": "No task_name specified"}

    # Convert event to JSON-serializable format (UUIDs to strings)
    def serialize(obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    event_json = json.loads(json.dumps(event, default=serialize))

    task_params = config.get("task_params", {})
    task_params["event_id"] = str(event.get("id"))
    task_params["event"] = event_json

    from substrate.core.config import DATABASE_URL

    try:
        from absurd_sdk import Absurd
        absurd = Absurd(DATABASE_URL, queue_name="default")
        result = absurd.spawn(task_name, task_params, queue="default")
        return {"success": True, "task_id": str(result.get("task_id"))}
    except Exception as e:
        return {"success": False, "error": f"Failed to spawn task: {e}"}
