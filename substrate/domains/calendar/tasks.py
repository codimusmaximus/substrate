"""Calendar domain background tasks."""
from datetime import datetime, timezone
from uuid import uuid4

from substrate.core.worker.registry import register_task
from substrate.core.db.connection import get_connection


def generate_ics(event: dict, attendees: list = None) -> str:
    """
    Generate an iCalendar (.ics) file content for an event.

    Args:
        event: Event dict with title, starts_at, ends_at, description, location
        attendees: List of attendee dicts with email, name

    Returns:
        ICS file content as string
    """
    uid = f"{event['id']}@substrate.local"
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Parse timestamps
    starts_at = event['starts_at']
    ends_at = event['ends_at']

    if isinstance(starts_at, str):
        starts_at = datetime.fromisoformat(starts_at.replace('Z', '+00:00'))
    if isinstance(ends_at, str):
        ends_at = datetime.fromisoformat(ends_at.replace('Z', '+00:00'))

    dtstart = starts_at.strftime("%Y%m%dT%H%M%SZ")
    dtend = ends_at.strftime("%Y%m%dT%H%M%SZ")

    # Build ICS content
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Substrate//Calendar//EN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{_escape_ics(event.get('title', 'Meeting'))}",
    ]

    if event.get('description'):
        lines.append(f"DESCRIPTION:{_escape_ics(event['description'])}")

    if event.get('location'):
        lines.append(f"LOCATION:{_escape_ics(event['location'])}")

    # Add attendees
    if attendees:
        for att in attendees:
            name = att.get('name', att.get('email', ''))
            email = att.get('email', '')
            role = "REQ-PARTICIPANT"
            if att.get('is_organizer'):
                role = "CHAIR"
            elif att.get('is_optional'):
                role = "OPT-PARTICIPANT"
            lines.append(f"ATTENDEE;ROLE={role};CN={_escape_ics(name)}:mailto:{email}")

    lines.extend([
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ])

    return "\r\n".join(lines)


def _escape_ics(text: str) -> str:
    """Escape special characters for ICS format."""
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def format_event_email(event: dict, template: str = "invite") -> tuple[str, str]:
    """
    Format event details for email.

    Args:
        event: Event dict
        template: 'invite', 'reminder', 'update', 'cancel'

    Returns:
        Tuple of (subject, html_body)
    """
    title = event.get('title', 'Meeting')
    starts_at = event.get('starts_at')
    location = event.get('location', '')
    description = event.get('description', '')

    if isinstance(starts_at, str):
        starts_at = datetime.fromisoformat(starts_at.replace('Z', '+00:00'))

    date_str = starts_at.strftime("%A, %B %d, %Y at %I:%M %p")

    if template == "invite":
        subject = f"Invitation: {title}"
        html = f"""
        <h2>You're invited to: {title}</h2>
        <p><strong>When:</strong> {date_str}</p>
        {"<p><strong>Where:</strong> " + location + "</p>" if location else ""}
        {"<p><strong>Details:</strong><br>" + description.replace(chr(10), '<br>') + "</p>" if description else ""}
        <p>Please reply to confirm your attendance.</p>
        """
    elif template == "reminder":
        subject = f"Reminder: {title}"
        html = f"""
        <h2>Reminder: {title}</h2>
        <p><strong>When:</strong> {date_str}</p>
        {"<p><strong>Where:</strong> " + location + "</p>" if location else ""}
        <p>This event is coming up soon.</p>
        """
    elif template == "update":
        subject = f"Updated: {title}"
        html = f"""
        <h2>Event Updated: {title}</h2>
        <p><strong>When:</strong> {date_str}</p>
        {"<p><strong>Where:</strong> " + location + "</p>" if location else ""}
        <p>This event has been updated.</p>
        """
    elif template == "cancel":
        subject = f"Cancelled: {title}"
        html = f"""
        <h2>Event Cancelled: {title}</h2>
        <p>The following event has been cancelled:</p>
        <p><strong>{title}</strong></p>
        <p>Originally scheduled for: {date_str}</p>
        """
    else:
        subject = title
        html = f"<p>{description}</p>"

    return subject, html


@register_task("calendar.send_invite")
def send_invite_task(params, ctx):
    """
    Send invite email to attendees.

    Args:
        params: Dict with event_id and optional attendee_email
        ctx: Absurd task context
    """
    from substrate.domains.calendar.tools import get_event, mark_invite_sent

    event_id = params.get("event_id")
    attendee_email = params.get("attendee_email")

    event = get_event(event_id)
    if not event:
        return {"error": f"Event {event_id} not found"}

    attendees = event.get('attendees', [])
    if not attendees:
        return {"skipped": "No attendees"}

    # Filter to specific attendee if specified
    if attendee_email:
        attendees = [a for a in attendees if a['email'] == attendee_email]

    # Filter to unsent invites
    to_send = [a for a in attendees if not a.get('invite_sent')]
    if not to_send:
        return {"skipped": "All invites already sent"}

    # Generate ICS
    ics_content = generate_ics(event, event.get('attendees', []))

    # Format email
    subject, html = format_event_email(event, template="invite")

    sent = 0
    errors = []

    for attendee in to_send:
        email = attendee['email']
        try:
            # Send calendar invite with ICS attachment
            from substrate.integrations.resend.client import send_calendar_invite
            ctx.step(f"send-{email}", lambda e=email: send_calendar_invite(
                to=e,
                subject=subject,
                html=html,
                ics_content=ics_content,
            ))
            ctx.step(f"mark-sent-{email}", lambda e=email: mark_invite_sent(event_id, e))
            sent += 1
        except Exception as e:
            errors.append({"email": email, "error": str(e)})

    return {"sent": sent, "errors": errors}


@register_task("calendar.send_reminders")
def send_reminders_task(params, ctx):
    """
    Check for events needing reminders and send them.

    Args:
        params: Dict with optional limit
        ctx: Absurd task context
    """
    from substrate.domains.calendar.tools import get_events_needing_reminder, mark_reminder_sent

    limit = params.get("limit", 50)
    events = get_events_needing_reminder()[:limit]

    if not events:
        return {"sent": 0, "message": "No reminders needed"}

    sent = 0
    errors = []

    for event in events:
        event_id = str(event['id'])
        try:
            # Get full event with attendees
            with get_connection() as conn:
                attendees = conn.execute("""
                    SELECT email, name FROM calendar.attendees
                    WHERE event_id = %s
                """, (event_id,)).fetchall()

            emails = [a['email'] for a in attendees]

            if emails:
                from substrate.integrations.resend.client import send_email
                subject, html = format_event_email(event, template="reminder")
                ctx.step(f"send-reminder-{event_id}", lambda: send_email(
                    to=emails,
                    subject=subject,
                    html=html,
                ))

            ctx.step(f"mark-reminder-{event_id}", lambda: mark_reminder_sent(event_id))
            sent += 1

        except Exception as e:
            errors.append({"event_id": event_id, "error": str(e)})

    return {"sent": sent, "errors": errors}


@register_task("calendar.process_response")
def process_response_task(params, ctx):
    """
    Process a calendar response email and update attendee status.

    Parses email subject like "Accepted: Meeting with Alexander" to:
    1. Extract response type (accepted/declined/tentative)
    2. Extract event title
    3. Find matching calendar event
    4. Update attendee status based on sender email

    Args:
        params: Dict with event_id and event
        ctx: Absurd task context
    """
    import re
    from substrate.domains.calendar.tools import update_attendee_status

    event_id = params.get("event_id")
    event = params.get("event")

    # Get event data if not passed
    if not event:
        with get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM events.events WHERE id = %s
            """, (event_id,)).fetchone()
            if not row:
                return {"error": f"Event {event_id} not found"}
            event = dict(row)

    subject = event.get("email_subject", "")
    sender = event.get("email_from", "")

    if not subject or not sender:
        return {"error": "Missing subject or sender"}

    # Parse response type and event title from subject
    # Patterns: "Accepted: Event Title", "Declined: Event Title", "Tentative: Event Title"
    match = re.match(r"^(Accepted|Declined|Tentative):\s*(.+)$", subject, re.IGNORECASE)
    if not match:
        return {"error": f"Could not parse response from subject: {subject}"}

    response_type = match.group(1).lower()
    event_title = match.group(2).strip()

    # Remove any "Invitation: " prefix if present (reply to invite)
    if event_title.lower().startswith("invitation:"):
        event_title = event_title[11:].strip()

    # Map response type to attendee status
    status_map = {
        "accepted": "accepted",
        "declined": "declined",
        "tentative": "tentative",
    }
    new_status = status_map.get(response_type)

    # Find calendar event by title match
    with get_connection() as conn:
        calendar_event = conn.execute("""
            SELECT id, title FROM calendar.events
            WHERE LOWER(title) = LOWER(%s)
            ORDER BY starts_at DESC
            LIMIT 1
        """, (event_title,)).fetchone()

    if not calendar_event:
        return {
            "error": f"No calendar event found matching title: {event_title}",
            "parsed": {"response": response_type, "title": event_title, "sender": sender}
        }

    calendar_event_id = str(calendar_event["id"])

    # Update attendee status
    result = ctx.step("update-attendee", lambda: update_attendee_status(
        event_id=calendar_event_id,
        email=sender,
        status=new_status,
    ))

    if not result:
        return {
            "error": f"Attendee {sender} not found for event {event_title}",
            "calendar_event_id": calendar_event_id,
        }

    return {
        "success": True,
        "calendar_event_id": calendar_event_id,
        "attendee_email": sender,
        "new_status": new_status,
        "event_title": event_title,
    }


@register_task("calendar.create_interaction")
def create_interaction_task(params, ctx):
    """
    Create a CRM interaction record after a meeting.

    Args:
        params: Dict with event_id
        ctx: Absurd task context
    """
    from substrate.domains.calendar.tools import get_event
    from substrate.domains.crm.tools import log_interaction

    event_id = params.get("event_id")
    event = get_event(event_id)
    if not event:
        return {"error": f"Event {event_id} not found"}

    # Only create interaction if there's a linked contact or company
    contact_id = event.get('contact_id')
    company_id = event.get('company_id')

    if not contact_id and not company_id:
        return {"skipped": "No linked contact or company"}

    # Map event type to interaction type
    interaction_type = "meeting"
    if event.get('type') == 'call':
        interaction_type = "call"

    # Calculate duration
    starts_at = event.get('starts_at')
    ends_at = event.get('ends_at')
    duration_minutes = None

    if starts_at and ends_at:
        if isinstance(starts_at, str):
            starts_at = datetime.fromisoformat(starts_at.replace('Z', '+00:00'))
        if isinstance(ends_at, str):
            ends_at = datetime.fromisoformat(ends_at.replace('Z', '+00:00'))
        duration_minutes = int((ends_at - starts_at).total_seconds() / 60)

    # Get attendee list for data
    attendees = event.get('attendees', [])
    attendee_info = [{"email": a['email'], "name": a.get('name'), "status": a.get('status')}
                     for a in attendees]

    interaction = ctx.step("log-interaction", lambda: log_interaction(
        type=interaction_type,
        contact_id=contact_id,
        company_id=company_id,
        subject=event.get('title'),
        content=event.get('description'),
        occurred_at=event.get('starts_at'),
        duration_minutes=duration_minutes,
        data={
            "calendar_event_id": str(event['id']),
            "location": event.get('location'),
            "attendees": attendee_info,
        }
    ))

    return {"interaction_id": str(interaction['id'])}
