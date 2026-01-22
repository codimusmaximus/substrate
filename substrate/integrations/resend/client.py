"""Resend API client for receiving emails."""
import os
import requests
from typing import Iterator


RESEND_API_URL = "https://api.resend.com"


def get_api_key() -> str:
    """Get Resend API key from environment."""
    return os.getenv("RESEND_API_KEY", "")


def list_received_emails(limit: int = 100, after: str = None) -> dict:
    """
    List received emails from Resend.

    Args:
        limit: Max emails to retrieve (1-100)
        after: Cursor for pagination (email ID to start after)

    Returns:
        API response with 'data' list and 'has_more' flag
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("RESEND_API_KEY not configured")

    params = {"limit": min(limit, 100)}
    if after:
        params["after"] = after

    response = requests.get(
        f"{RESEND_API_URL}/emails/receiving",
        headers={"Authorization": f"Bearer {api_key}"},
        params=params,
    )
    response.raise_for_status()
    return response.json()


def get_received_email(email_id: str) -> dict:
    """
    Get a single received email with full content.

    Args:
        email_id: The email ID from list response

    Returns:
        Full email data including html/text content
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("RESEND_API_KEY not configured")

    response = requests.get(
        f"{RESEND_API_URL}/emails/receiving/{email_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    response.raise_for_status()
    return response.json()


def iter_all_emails(limit: int = 100) -> Iterator[dict]:
    """
    Iterate through all received emails with pagination.

    Args:
        limit: Batch size per request

    Yields:
        Email dicts from the API
    """
    after = None

    while True:
        result = list_received_emails(limit=limit, after=after)
        emails = result.get("data", [])

        for email in emails:
            yield email

        if not result.get("has_more") or not emails:
            break

        after = emails[-1]["id"]


def get_default_from_email() -> str:
    """Get default sender email from environment."""
    name = os.getenv("DEFAULT_FROM_NAME", "Substrate")
    email = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
    return f"{name} <{email}>"


def send_email(
    to: str | list[str],
    subject: str,
    html: str = None,
    text: str = None,
    from_email: str = None,
    attachments: list[dict] = None,
) -> dict:
    """
    Send an email via Resend.

    Args:
        to: Recipient email(s)
        subject: Email subject
        html: HTML body (optional if text provided)
        text: Plain text body (optional if html provided)
        from_email: Sender address (uses DEFAULT_FROM_EMAIL env var if not specified)
        attachments: List of attachments, each with:
            - filename: str
            - content: str (base64 encoded) or raw content
            - content_type: str (optional, e.g., "text/calendar")

    Returns:
        API response with 'id' of sent email
    """
    import base64

    api_key = get_api_key()
    if not api_key:
        raise ValueError("RESEND_API_KEY not configured")

    payload = {
        "from": from_email or get_default_from_email(),
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
    }
    if html:
        payload["html"] = html
    if text:
        payload["text"] = text

    if attachments:
        payload["attachments"] = []
        for att in attachments:
            content = att.get("content", "")
            # Base64 encode if it's raw content (not already encoded)
            if isinstance(content, str) and not att.get("is_base64"):
                content = base64.b64encode(content.encode()).decode()
            attachment_obj = {
                "filename": att.get("filename", "attachment"),
                "content": content,
            }
            # Include content_type if specified (important for calendar invites)
            if att.get("content_type"):
                attachment_obj["content_type"] = att["content_type"]
            payload["attachments"].append(attachment_obj)

    response = requests.post(
        f"{RESEND_API_URL}/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
    )
    response.raise_for_status()
    return response.json()


def send_calendar_invite(
    to: str | list[str],
    subject: str,
    html: str,
    ics_content: str,
    from_email: str = None,
) -> dict:
    """
    Send a calendar invite email with .ics attachment.

    Uses content_type with method=REQUEST so Outlook/Gmail show
    Accept/Decline buttons instead of just an import option.

    Args:
        to: Recipient email(s)
        subject: Email subject
        html: HTML body
        ics_content: iCalendar file content
        from_email: Sender address

    Returns:
        API response with 'id' of sent email
    """
    return send_email(
        to=to,
        subject=subject,
        html=html,
        from_email=from_email,
        attachments=[{
            "filename": "invite.ics",
            "content": ics_content,
            "content_type": 'text/calendar; charset="UTF-8"; method=REQUEST',
        }]
    )
