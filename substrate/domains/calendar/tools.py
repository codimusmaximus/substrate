"""AI tools for calendar domain."""
from datetime import datetime, timedelta
from typing import Any

from psycopg.types.json import Json
from substrate.core.db.connection import get_connection


def query_events(
    start_date: str = None,
    end_date: str = None,
    type: str = None,
    status: str = None,
    contact_id: str = None,
    company_id: str = None,
    search: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search events by date range, type, or linked contact/company.

    Args:
        start_date: Start of date range (ISO format, defaults to today)
        end_date: End of date range (ISO format)
        type: Filter by type (meeting, call, reminder, focus, appointment)
        status: Filter by status (tentative, confirmed, cancelled)
        contact_id: Filter by linked contact
        company_id: Filter by linked company
        search: Search in title or description
        limit: Max results

    Returns:
        List of events with basic info
    """
    conditions = []
    params = []

    if start_date:
        conditions.append("starts_at >= %s::timestamptz")
        params.append(start_date)
    if end_date:
        conditions.append("starts_at <= %s::timestamptz")
        params.append(end_date)
    if type:
        conditions.append("type = %s")
        params.append(type)
    if status:
        conditions.append("status = %s")
        params.append(status)
    if contact_id:
        conditions.append("contact_id = %s")
        params.append(contact_id)
    if company_id:
        conditions.append("company_id = %s")
        params.append(company_id)
    if search:
        conditions.append("(title ILIKE %s OR description ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, title, type, status, starts_at, ends_at, all_day,
                   location, contact_id, company_id, tags, created_at
            FROM calendar.events
            WHERE {where}
            ORDER BY starts_at
            LIMIT %s
        """, params).fetchall()

    return [dict(r) for r in rows]


def get_event(event_id: str) -> dict | None:
    """
    Get full event details by ID, including attendees.

    Args:
        event_id: UUID of the event

    Returns:
        Event with full details and attendees list
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM calendar.events WHERE id = %s",
            (event_id,)
        ).fetchone()

        if not row:
            return None

        event = dict(row)

        # Get attendees
        attendees = conn.execute("""
            SELECT id, email, name, status, is_organizer, is_optional,
                   contact_id, invite_sent, invite_sent_at
            FROM calendar.attendees
            WHERE event_id = %s
            ORDER BY is_organizer DESC, name
        """, (event_id,)).fetchall()

        event['attendees'] = [dict(a) for a in attendees]

    return event


def get_today_events() -> list[dict]:
    """
    Get today's events.

    Returns:
        List of events scheduled for today
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, type, status, starts_at, ends_at, all_day,
                   location, contact_id, company_id, tags
            FROM calendar.today
        """).fetchall()

    return [dict(r) for r in rows]


def get_upcoming_events(days: int = 7, limit: int = 20) -> list[dict]:
    """
    Get upcoming events.

    Args:
        days: Number of days to look ahead (default 7)
        limit: Max results

    Returns:
        List of upcoming events
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, type, status, starts_at, ends_at, all_day,
                   location, contact_id, company_id, tags
            FROM calendar.events
            WHERE status != 'cancelled'
              AND starts_at >= now()
              AND starts_at <= now() + %s * interval '1 day'
            ORDER BY starts_at
            LIMIT %s
        """, (days, limit)).fetchall()

    return [dict(r) for r in rows]


def create_event(
    title: str,
    starts_at: str,
    ends_at: str,
    type: str = "meeting",
    status: str = "confirmed",
    description: str = None,
    location: str = None,
    all_day: bool = False,
    contact_id: str = None,
    company_id: str = None,
    remind_before_minutes: int = None,
    tags: list = None,
    data: dict = None,
    attendees: list = None,
) -> dict:
    """
    Create a new calendar event.

    Args:
        title: Event title (required)
        starts_at: Start time (ISO format, required)
        ends_at: End time (ISO format, required)
        type: meeting, call, reminder, focus, appointment
        status: tentative, confirmed, cancelled
        description: Event description
        location: Physical address or video link
        all_day: Is this an all-day event
        contact_id: Link to primary CRM contact
        company_id: Link to CRM company
        remind_before_minutes: Send reminder N minutes before (e.g., 15, 60)
        tags: List of tags
        data: Custom fields (video_link, notes, etc.)
        attendees: List of dicts with email, name, is_organizer, is_optional

    Returns:
        Created event with attendees
    """
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO calendar.events
            (title, starts_at, ends_at, type, status, description, location,
             all_day, contact_id, company_id, remind_before_minutes, tags, data)
            VALUES (%s, %s::timestamptz, %s::timestamptz, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            title, starts_at, ends_at, type, status, description, location,
            all_day, contact_id, company_id, remind_before_minutes,
            tags or [], Json(data or {})
        )).fetchone()

        event = dict(row)
        event_id = event['id']

        # Add attendees if provided
        if attendees:
            for att in attendees:
                conn.execute("""
                    INSERT INTO calendar.attendees
                    (event_id, email, name, contact_id, is_organizer, is_optional)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    event_id,
                    att.get('email'),
                    att.get('name'),
                    att.get('contact_id'),
                    att.get('is_organizer', False),
                    att.get('is_optional', False),
                ))

        conn.commit()

    return get_event(event_id)


def update_event(event_id: str, **kwargs) -> dict | None:
    """
    Update an event.

    Args:
        event_id: UUID of event
        **kwargs: Fields to update (title, starts_at, ends_at, type, status,
                  description, location, all_day, contact_id, company_id,
                  remind_before_minutes, tags, data)

    Returns:
        Updated event
    """
    allowed = ['title', 'starts_at', 'ends_at', 'type', 'status', 'description',
               'location', 'all_day', 'contact_id', 'company_id',
               'remind_before_minutes', 'tags', 'data']
    updates = []
    params = []

    for key, value in kwargs.items():
        if key in allowed and value is not None:
            if key in ['starts_at', 'ends_at']:
                updates.append(f"{key} = %s::timestamptz")
            else:
                updates.append(f"{key} = %s")

            if key == 'data':
                params.append(Json(value))
            else:
                params.append(value)

    if not updates:
        return get_event(event_id)

    updates.append("updated_at = %s")
    params.append(datetime.utcnow())
    params.append(event_id)

    with get_connection() as conn:
        row = conn.execute(f"""
            UPDATE calendar.events
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING *
        """, params).fetchone()
        conn.commit()

    return get_event(event_id) if row else None


def cancel_event(event_id: str) -> dict | None:
    """
    Cancel an event (sets status to 'cancelled').

    Args:
        event_id: UUID of event

    Returns:
        Updated event
    """
    with get_connection() as conn:
        row = conn.execute("""
            UPDATE calendar.events
            SET status = 'cancelled', updated_at = %s
            WHERE id = %s
            RETURNING *
        """, (datetime.utcnow(), event_id)).fetchone()
        conn.commit()

    return dict(row) if row else None


def delete_event(event_id: str) -> bool:
    """
    Permanently delete an event.

    Args:
        event_id: UUID of event

    Returns:
        True if deleted
    """
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM calendar.events WHERE id = %s",
            (event_id,)
        )
        conn.commit()
    return result.rowcount > 0


def add_attendee(
    event_id: str,
    email: str,
    name: str = None,
    contact_id: str = None,
    is_organizer: bool = False,
    is_optional: bool = False,
) -> dict:
    """
    Add an attendee to an event.

    Args:
        event_id: UUID of event
        email: Attendee email (required)
        name: Attendee name
        contact_id: Link to CRM contact
        is_organizer: Is this the organizer
        is_optional: Is attendance optional

    Returns:
        Created attendee
    """
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO calendar.attendees
            (event_id, email, name, contact_id, is_organizer, is_optional)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id, email) DO UPDATE SET
                name = EXCLUDED.name,
                contact_id = COALESCE(EXCLUDED.contact_id, calendar.attendees.contact_id),
                is_organizer = EXCLUDED.is_organizer,
                is_optional = EXCLUDED.is_optional
            RETURNING *
        """, (event_id, email, name, contact_id, is_organizer, is_optional)).fetchone()
        conn.commit()

    return dict(row)


def update_attendee_status(
    event_id: str,
    email: str,
    status: str,
) -> dict | None:
    """
    Update an attendee's response status.

    Args:
        event_id: UUID of event
        email: Attendee email
        status: pending, accepted, declined, tentative

    Returns:
        Updated attendee (with UUIDs as strings for JSON serialization)
    """
    with get_connection() as conn:
        row = conn.execute("""
            UPDATE calendar.attendees
            SET status = %s
            WHERE event_id = %s AND email = %s
            RETURNING *
        """, (status, event_id, email)).fetchone()
        conn.commit()

    if not row:
        return None

    # Convert to JSON-serializable dict
    from datetime import datetime as dt
    result = {}
    for key, value in dict(row).items():
        if hasattr(value, 'hex'):  # UUID
            result[key] = str(value)
        elif isinstance(value, dt):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def remove_attendee(event_id: str, email: str) -> bool:
    """
    Remove an attendee from an event.

    Args:
        event_id: UUID of event
        email: Attendee email

    Returns:
        True if removed
    """
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM calendar.attendees WHERE event_id = %s AND email = %s",
            (event_id, email)
        )
        conn.commit()
    return result.rowcount > 0


def get_events_needing_reminder() -> list[dict]:
    """
    Get events that need reminder emails sent.

    Returns:
        List of events where reminder time has passed but reminder not sent
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM calendar.needs_reminder
        """).fetchall()

    return [dict(r) for r in rows]


def mark_reminder_sent(event_id: str) -> bool:
    """
    Mark an event's reminder as sent.

    Args:
        event_id: UUID of event

    Returns:
        True if updated
    """
    with get_connection() as conn:
        result = conn.execute("""
            UPDATE calendar.events
            SET reminder_sent = TRUE, updated_at = %s
            WHERE id = %s
        """, (datetime.utcnow(), event_id))
        conn.commit()
    return result.rowcount > 0


def mark_invite_sent(event_id: str, email: str) -> bool:
    """
    Mark an attendee's invite as sent.

    Args:
        event_id: UUID of event
        email: Attendee email

    Returns:
        True if updated
    """
    with get_connection() as conn:
        result = conn.execute("""
            UPDATE calendar.attendees
            SET invite_sent = TRUE, invite_sent_at = %s
            WHERE event_id = %s AND email = %s
        """, (datetime.utcnow(), event_id, email))
        conn.commit()
    return result.rowcount > 0


# Export tools for AI discovery
TOOLS = [
    query_events,
    get_event,
    get_today_events,
    get_upcoming_events,
    create_event,
    update_event,
    cancel_event,
    delete_event,
    add_attendee,
    update_attendee_status,
    remove_attendee,
]
