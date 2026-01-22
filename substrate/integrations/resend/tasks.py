"""Resend integration background tasks."""
from substrate.core.worker.registry import register_task
from substrate.core.db.connection import get_connection


@register_task("resend.sync")
def sync_emails(ctx, process_events: bool = True):
    """
    Sync received emails from Resend to events table.

    Args:
        process_events: Whether to immediately process through router
    """
    from substrate.integrations.resend.client import list_received_emails, get_received_email
    from substrate.domains.events.router import create_event, process_event

    # Get already-synced email IDs
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT source_id FROM events.events
            WHERE source = 'resend'
        """).fetchall()
    synced_ids = {row["source_id"] for row in rows}

    # Fetch from Resend
    result = list_received_emails(limit=100)
    emails = result.get("data", [])

    created = 0
    processed = 0
    errors = []

    for email_meta in emails:
        email_id = email_meta["id"]

        # Skip if already synced
        if email_id in synced_ids:
            continue

        try:
            # Fetch full email content
            email = get_received_email(email_id)

            # Create event
            event = create_event(
                source="resend",
                source_id=email_id,
                event_type="email.received",
                payload=email,
                email_from=email.get("from", ""),
                email_to=", ".join(email.get("to", [])),
                email_subject=email.get("subject", ""),
                email_body=email.get("text") or email.get("html", ""),
                email_date=email.get("created_at"),
            )
            created += 1

            # Process through router
            if process_events and event.get("status") == "pending":
                result = process_event(str(event["id"]))
                if result.get("status") == "processed":
                    processed += 1

        except Exception as e:
            errors.append({"email_id": email_id, "error": str(e)})

    return {
        "created": created,
        "processed": processed,
        "skipped": len(synced_ids),
        "errors": errors,
    }


def _do_sync() -> dict:
    """Execute a single sync (for scheduler)."""
    from substrate.integrations.resend.client import list_received_emails, get_received_email
    from substrate.domains.events.router import create_event, process_event

    # Get already-synced email IDs
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT source_id FROM events.events
            WHERE source = 'resend'
        """).fetchall()
    synced_ids = {row["source_id"] for row in rows}

    try:
        result = list_received_emails(limit=100)
        emails = result.get("data", [])
    except Exception as e:
        return {"error": str(e)}

    created = 0
    processed = 0

    for email_meta in emails:
        email_id = email_meta["id"]

        if email_id in synced_ids:
            continue

        try:
            email = get_received_email(email_id)

            event = create_event(
                source="resend",
                source_id=email_id,
                event_type="email.received",
                payload=email,
                email_from=email.get("from", ""),
                email_to=", ".join(email.get("to", [])),
                email_subject=email.get("subject", ""),
                email_body=email.get("text") or email.get("html", ""),
                email_date=email.get("created_at"),
            )
            created += 1

            if event.get("status") == "pending":
                result = process_event(str(event["id"]))
                if result.get("status") == "processed":
                    processed += 1

        except Exception:
            pass  # Continue on individual email errors

    return {"created": created, "processed": processed}
