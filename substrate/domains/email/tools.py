"""Email domain tools - send and receive emails.

This module provides tools for:
- Sending emails via Resend
- Viewing received emails (synced from Resend)
- Managing email threads
"""
from substrate.core.db.connection import get_connection
from substrate.integrations.resend.client import send_email as resend_send


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    html: bool = True,
    from_email: str = None,
    reply_to: str = None,
    confirm: bool = False,
) -> dict:
    """
    Send an email via Resend.

    IMPORTANT: Requires confirm=True to actually send. Without confirmation,
    returns a preview for user approval.

    Args:
        to: Recipient email(s)
        subject: Email subject
        body: Email body (HTML by default, or plain text)
        html: If True, body is HTML; if False, plain text
        from_email: Sender address (uses DEFAULT_FROM_EMAIL env var if not specified)
        reply_to: Reply-to address
        confirm: Must be True to actually send (safety measure)

    Returns:
        Dict with preview (if not confirmed) or send result (if confirmed)
    """
    # Default sender from environment
    if not from_email:
        from substrate.integrations.resend.client import get_default_from_email
        from_email = get_default_from_email()

    # Preview mode - ask for confirmation
    if not confirm:
        preview = body[:500] + "..." if len(body) > 500 else body
        return {
            "status": "awaiting_confirmation",
            "message": "Review the email below. Call again with confirm=True to send.",
            "preview": {
                "from": from_email,
                "to": to,
                "subject": subject,
                "body_preview": preview,
                "body_type": "html" if html else "text",
            }
        }

    # Confirmed - actually send
    try:
        if html:
            result = resend_send(to=to, subject=subject, html=body, from_email=from_email)
        else:
            result = resend_send(to=to, subject=subject, text=body, from_email=from_email)
        return {"success": True, "status": "sent", "id": result.get("id"), "to": to, "subject": subject}
    except Exception as e:
        return {"success": False, "status": "error", "error": str(e)}


def list_emails(
    inbox: str = None,
    from_address: str = None,
    search: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    List received emails.

    Args:
        inbox: Filter by recipient inbox (e.g., 'support@yourdomain.com')
        from_address: Filter by sender (partial match)
        search: Search in subject or body
        limit: Max results

    Returns:
        List of email summaries
    """
    with get_connection() as conn:
        conditions = ["event_type = 'email.received'"]
        params = []

        if inbox:
            conditions.append("email_to ILIKE %s")
            params.append(f"%{inbox}%")

        if from_address:
            conditions.append("email_from ILIKE %s")
            params.append(f"%{from_address}%")

        if search:
            conditions.append("(email_subject ILIKE %s OR email_body ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])

        params.append(limit)

        rows = conn.execute(f"""
            SELECT id, email_from, email_to, email_subject,
                   LEFT(email_body, 200) as preview,
                   status, created_at
            FROM events.events
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT %s
        """, params).fetchall()

    return [dict(r) for r in rows]


def get_email(email_id: str) -> dict | None:
    """
    Get full email content by ID.

    Args:
        email_id: UUID of the email event

    Returns:
        Full email with body and metadata
    """
    with get_connection() as conn:
        row = conn.execute("""
            SELECT id, email_from, email_to, email_subject, email_body,
                   payload, status, created_at
            FROM events.events
            WHERE id = %s AND event_type = 'email.received'
        """, (email_id,)).fetchone()

    return dict(row) if row else None


def reply_to_email(
    email_id: str,
    body: str,
    html: bool = True,
    confirm: bool = False,
) -> dict:
    """
    Reply to a received email.

    IMPORTANT: Requires confirm=True to actually send.

    Args:
        email_id: UUID of the email to reply to
        body: Reply body
        html: If True, body is HTML
        confirm: Must be True to actually send

    Returns:
        Preview (if not confirmed) or send result (if confirmed)
    """
    email = get_email(email_id)
    if not email:
        return {"success": False, "error": "Email not found"}

    # Build reply subject
    subject = email["email_subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # Get from address (first recipient of original email)
    from_email = email["email_to"].split(",")[0].strip() if email["email_to"] else None

    # Reply to sender
    return send_email(
        to=email["email_from"],
        subject=subject,
        body=body,
        html=html,
        from_email=from_email,
        confirm=confirm,
    )


def get_email_stats() -> dict:
    """
    Get email statistics.

    Returns:
        Dict with counts by status and inbox
    """
    with get_connection() as conn:
        # By status
        status_rows = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM events.events
            WHERE event_type = 'email.received'
            GROUP BY status
        """).fetchall()

        # By inbox (top 10)
        inbox_rows = conn.execute("""
            SELECT email_to, COUNT(*) as count
            FROM events.events
            WHERE event_type = 'email.received'
            GROUP BY email_to
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()

        # Recent activity
        recent = conn.execute("""
            SELECT COUNT(*) as count
            FROM events.events
            WHERE event_type = 'email.received'
              AND created_at > NOW() - INTERVAL '24 hours'
        """).fetchone()

    return {
        "by_status": {r["status"]: r["count"] for r in status_rows},
        "by_inbox": {r["email_to"]: r["count"] for r in inbox_rows},
        "last_24h": recent["count"] if recent else 0,
    }
