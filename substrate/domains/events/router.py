"""Events router - routes events through rules to actions.

This module provides an extensible routing system. Currently uses rule-based
matching, but designed to support LLM-based routing in the future.
"""
from datetime import datetime
from typing import Any

from psycopg.types.json import Json
from substrate.core.db.connection import get_connection
from substrate.domains.events.logic import matches_conditions


def get_enabled_rules() -> list[dict]:
    """Get all enabled rules, sorted by priority (highest first)."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, name, conditions, action, action_config
            FROM events.rules
            WHERE enabled = true
            ORDER BY priority DESC, created_at ASC
        """).fetchall()
    return [dict(r) for r in rows]


def route_event(event: dict) -> dict | None:
    """
    Route an event through rules to determine action.

    This is the main routing function. It checks each enabled rule in priority
    order and returns the first match.

    Args:
        event: Event dict with keys like email_from, email_subject, etc.

    Returns:
        Dict with rule_id, action, action_config if a rule matched.
        None if no rule matched.

    Future: This function can be extended to use LLM-based routing when
    no rules match, or to use LLM for complex classification.
    """
    rules = get_enabled_rules()

    for rule in rules:
        conditions = rule.get("conditions", {})
        if matches_conditions(event, conditions):
            return {
                "rule_id": str(rule["id"]),
                "rule_name": rule["name"],
                "action": rule["action"],
                "action_config": rule.get("action_config") or {},
            }

    # No rule matched
    return None


def process_event(event_id: str) -> dict:
    """
    Process a single event: route it and execute the action.

    Args:
        event_id: UUID of the event to process

    Returns:
        Dict with processing result
    """
    from substrate.domains.events.actions import execute_action

    with get_connection() as conn:
        # Fetch the event
        event = conn.execute(
            "SELECT * FROM events.events WHERE id = %s",
            (event_id,)
        ).fetchone()

        if not event:
            return {"error": "Event not found"}

        event = dict(event)

        if event["status"] != "pending":
            return {"error": f"Event already processed: {event['status']}"}

        # Route the event
        route_result = route_event(event)

        if route_result is None:
            # No rule matched - mark as unmatched but don't fail
            conn.execute("""
                UPDATE events.events
                SET status = 'unmatched', routed_at = %s, updated_at = %s
                WHERE id = %s
            """, (datetime.utcnow(), datetime.utcnow(), event_id))
            conn.commit()
            return {"status": "unmatched", "event_id": event_id}

        # Update event with routing result
        conn.execute("""
            UPDATE events.events
            SET matched_rule_id = %s, route_result = %s, routed_at = %s, updated_at = %s
            WHERE id = %s
        """, (
            route_result["rule_id"],
            Json(route_result),
            datetime.utcnow(),
            datetime.utcnow(),
            event_id
        ))

        # Update rule stats
        conn.execute("""
            UPDATE events.rules
            SET match_count = match_count + 1, last_matched_at = %s
            WHERE id = %s
        """, (datetime.utcnow(), route_result["rule_id"]))

        conn.commit()

    # Execute the action
    action_result = execute_action(
        event_id=event_id,
        rule_id=route_result["rule_id"],
        action=route_result["action"],
        action_config=route_result["action_config"],
        event=event,
    )

    # Update event status based on action result
    with get_connection() as conn:
        new_status = "processed" if action_result.get("success") else "failed"
        conn.execute("""
            UPDATE events.events
            SET status = %s, updated_at = %s
            WHERE id = %s
        """, (new_status, datetime.utcnow(), event_id))
        conn.commit()

    return {
        "status": new_status,
        "event_id": event_id,
        "rule_id": route_result["rule_id"],
        "action": route_result["action"],
        "action_result": action_result,
    }


def _get_owner_for_inbox(conn, email_to: str | None) -> str | None:
    """Look up owner_id based on inbox email address."""
    if not email_to:
        return None
    # Handle comma-separated recipients, take first match
    for addr in email_to.split(","):
        addr = addr.strip().lower()
        row = conn.execute(
            "SELECT user_id FROM auth.inbox_members im "
            "JOIN auth.inboxes i ON i.id = im.inbox_id "
            "WHERE LOWER(i.email) = %s LIMIT 1",
            (addr,)
        ).fetchone()
        if row:
            return str(row["user_id"])
    return None


def create_event(
    source: str,
    source_id: str | None,
    event_type: str,
    payload: dict,
    email_from: str | None = None,
    email_to: str | None = None,
    email_subject: str | None = None,
    email_body: str | None = None,
    email_date: datetime | None = None,
    owner_id: str | None = None,
) -> dict:
    """
    Create a new event in the database.

    Args:
        source: Event source ('email', 'webhook', 'manual')
        source_id: External ID for deduplication
        event_type: Type of event ('email.received', etc.)
        payload: Full event payload as JSON
        email_*: Optional email-specific fields
        owner_id: Optional owner UUID (auto-detected from inbox if not provided)

    Returns:
        Created event dict
    """
    with get_connection() as conn:
        # Auto-detect owner from inbox if not provided
        if owner_id is None and email_to:
            owner_id = _get_owner_for_inbox(conn, email_to)

        row = conn.execute("""
            INSERT INTO events.events (
                source, source_id, event_type, payload,
                email_from, email_to, email_subject, email_body, email_date,
                owner_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source, source_id) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = now()
            RETURNING *
        """, (
            source, source_id, event_type, Json(payload),
            email_from, email_to, email_subject, email_body, email_date,
            owner_id
        )).fetchone()
        conn.commit()
    return dict(row)
