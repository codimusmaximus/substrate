"""AI tools for events domain - manage events and rules."""
import json
from datetime import datetime
from typing import Any

from psycopg.types.json import Json
from substrate.core.db.connection import get_connection


def query_events(
    status: str = None,
    source: str = None,
    email_from: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search events by status, source, or sender.

    Args:
        status: Filter by status (pending, processed, failed, unmatched, ignored)
        source: Filter by source (email, webhook, manual)
        email_from: Filter by sender email (partial match)
        limit: Maximum results to return

    Returns:
        List of events with id, source, status, email_from, email_subject, created_at
    """
    conditions = []
    params = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if source:
        conditions.append("source = %s")
        params.append(source)
    if email_from:
        conditions.append("email_from ILIKE %s")
        params.append(f"%{email_from}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, source, source_id, event_type, status,
                   email_from, email_subject, created_at
            FROM events.events
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s
        """, params).fetchall()

    return [dict(r) for r in rows]


def get_event(event_id: str) -> dict | None:
    """
    Get full details of an event by ID.

    Args:
        event_id: UUID of the event

    Returns:
        Full event dict or None if not found
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events.events WHERE id = %s",
            (event_id,)
        ).fetchone()

    return dict(row) if row else None


def list_rules(enabled_only: bool = True) -> list[dict]:
    """
    List all routing rules.

    Args:
        enabled_only: Only return enabled rules

    Returns:
        List of rules with id, name, enabled, priority, conditions, action
    """
    where = "WHERE enabled = true" if enabled_only else ""

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, name, description, enabled, priority,
                   conditions, action, action_config,
                   match_count, last_matched_at
            FROM events.rules
            {where}
            ORDER BY priority DESC, created_at ASC
        """).fetchall()

    return [dict(r) for r in rows]


def create_rule(
    name: str,
    conditions: dict,
    action: str,
    action_config: dict = None,
    description: str = None,
    priority: int = 0,
) -> dict:
    """
    Create a new routing rule.

    Args:
        name: Rule name
        conditions: Matching conditions dict, e.g.:
            - from_contains: Match sender containing string
            - from_equals: Match exact sender
            - subject_contains: Match subject containing string
            - subject_matches: Match subject with regex
            - body_contains: Match body containing string
            - has_attachment: Match if has attachments (true/false)
        action: Action to take: 'create_note', 'tag', 'ignore', 'spawn_task'
        action_config: Action-specific config, e.g.:
            - For create_note: {folder: 'Inbox', tags: ['email']}
            - For tag: {tags: ['important']}
            - For spawn_task: {task_name: 'myapp.process'}
        description: Optional rule description
        priority: Higher priority rules are checked first (default: 0)

    Returns:
        Created rule dict
    """
    if action_config is None:
        action_config = {}

    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO events.rules (name, description, priority, conditions, action, action_config)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (name, description, priority, Json(conditions), action, Json(action_config))).fetchone()
        conn.commit()

    return dict(row)


def update_rule(
    rule_id: str,
    name: str = None,
    conditions: dict = None,
    action: str = None,
    action_config: dict = None,
    description: str = None,
    priority: int = None,
    enabled: bool = None,
) -> dict:
    """
    Update an existing rule.

    Args:
        rule_id: UUID of the rule to update
        name: New name (optional)
        conditions: New conditions (optional)
        action: New action (optional)
        action_config: New action config (optional)
        description: New description (optional)
        priority: New priority (optional)
        enabled: Enable/disable rule (optional)

    Returns:
        Updated rule dict
    """
    updates = []
    params = []

    if name is not None:
        updates.append("name = %s")
        params.append(name)
    if conditions is not None:
        updates.append("conditions = %s")
        params.append(Json(conditions))
    if action is not None:
        updates.append("action = %s")
        params.append(action)
    if action_config is not None:
        updates.append("action_config = %s")
        params.append(Json(action_config))
    if description is not None:
        updates.append("description = %s")
        params.append(description)
    if priority is not None:
        updates.append("priority = %s")
        params.append(priority)
    if enabled is not None:
        updates.append("enabled = %s")
        params.append(enabled)

    if not updates:
        return get_rule(rule_id)

    updates.append("updated_at = %s")
    params.append(datetime.utcnow())
    params.append(rule_id)

    with get_connection() as conn:
        row = conn.execute(f"""
            UPDATE events.rules
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING *
        """, params).fetchone()
        conn.commit()

    return dict(row) if row else None


def delete_rule(rule_id: str) -> bool:
    """
    Delete a rule.

    Args:
        rule_id: UUID of the rule to delete

    Returns:
        True if deleted, False if not found
    """
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM events.rules WHERE id = %s RETURNING id",
            (rule_id,)
        ).fetchone()
        conn.commit()

    return result is not None


def get_rule(rule_id: str) -> dict | None:
    """
    Get a rule by ID.

    Args:
        rule_id: UUID of the rule

    Returns:
        Rule dict or None
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events.rules WHERE id = %s",
            (rule_id,)
        ).fetchone()

    return dict(row) if row else None


def reprocess_event(event_id: str) -> dict:
    """
    Reprocess an event through the router.

    Resets the event to pending status and processes it again.

    Args:
        event_id: UUID of the event to reprocess

    Returns:
        Processing result
    """
    from substrate.domains.events.router import process_event

    # Reset event status to pending
    with get_connection() as conn:
        conn.execute("""
            UPDATE events.events
            SET status = 'pending', matched_rule_id = NULL,
                route_result = NULL, routed_at = NULL, updated_at = %s
            WHERE id = %s
        """, (datetime.utcnow(), event_id))
        conn.commit()

    # Process the event
    return process_event(event_id)


def create_manual_event(
    event_type: str,
    payload: dict,
    email_from: str = None,
    email_to: str = None,
    email_subject: str = None,
    email_body: str = None,
) -> dict:
    """
    Create a manual event for testing rules.

    Args:
        event_type: Type of event (e.g., 'email.received', 'test')
        payload: Event payload data
        email_from: Optional sender for email-like events
        email_to: Optional recipient
        email_subject: Optional subject
        email_body: Optional body

    Returns:
        Created event dict
    """
    from substrate.domains.events.router import create_event
    import uuid

    return create_event(
        source="manual",
        source_id=str(uuid.uuid4()),
        event_type=event_type,
        payload=payload,
        email_from=email_from,
        email_to=email_to,
        email_subject=email_subject,
        email_body=email_body,
    )


# Export tools for AI discovery
TOOLS = [
    query_events,
    get_event,
    list_rules,
    create_rule,
    update_rule,
    delete_rule,
    reprocess_event,
    create_manual_event,
]
