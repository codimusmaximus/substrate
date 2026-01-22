"""Events domain background tasks."""
from substrate.core.worker.registry import register_task
from substrate.core.db.connection import get_connection


@register_task("events.process")
def process_event_task(ctx, event_id: str = None):
    """
    Process a single event through the router.

    Args:
        event_id: UUID of the event to process
    """
    from substrate.domains.events.router import process_event

    if not event_id:
        return {"error": "No event_id provided"}

    result = process_event(event_id)
    return result


@register_task("events.process_pending")
def process_pending_events(ctx, limit: int = 100):
    """
    Process all pending events.

    Args:
        limit: Maximum number of events to process in one batch
    """
    from substrate.domains.events.router import process_event

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id FROM events.events
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT %s
        """, (limit,)).fetchall()

    processed = 0
    failed = 0
    results = []

    for row in rows:
        event_id = str(row["id"])
        try:
            result = ctx.step(f"process-{event_id}", lambda: process_event(event_id))
            if result.get("status") == "processed":
                processed += 1
            else:
                failed += 1
            results.append(result)
        except Exception as e:
            failed += 1
            results.append({"event_id": event_id, "error": str(e)})

    return {
        "processed": processed,
        "failed": failed,
        "total": len(rows),
        "results": results,
    }
