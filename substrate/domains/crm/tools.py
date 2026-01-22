"""AI tools for CRM domain."""
from datetime import datetime
from typing import Any

from psycopg.types.json import Json
from substrate.core.db.connection import get_connection


# === CONTACTS ===

def query_contacts(
    type: str = None,
    status: str = None,
    company_id: str = None,
    search: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search contacts by type, status, or name/email.

    Args:
        type: Filter by type (lead, customer, investor, partner, vendor)
        status: Filter by status (active, inactive, churned, converted)
        company_id: Filter by company UUID
        search: Search in name or email
        limit: Max results

    Returns:
        List of contacts with basic info
    """
    conditions = []
    params = []

    if type:
        conditions.append("type = %s")
        params.append(type)
    if status:
        conditions.append("status = %s")
        params.append(status)
    if company_id:
        conditions.append("company_id = %s")
        params.append(company_id)
    if search:
        conditions.append("(name ILIKE %s OR email ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, name, email, phone, type, status, title, tags, created_at
            FROM crm.contacts
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s
        """, params).fetchall()

    return [dict(r) for r in rows]


def get_contact(contact_id: str) -> dict | None:
    """Get full contact details by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM crm.contacts WHERE id = %s",
            (contact_id,)
        ).fetchone()
    return dict(row) if row else None


def create_contact(
    name: str,
    email: str = None,
    phone: str = None,
    type: str = "lead",
    status: str = "active",
    company_id: str = None,
    title: str = None,
    source: str = None,
    tags: list = None,
    data: dict = None,
) -> dict:
    """
    Create a new contact.

    Args:
        name: Contact name (required)
        email: Email address
        phone: Phone number
        type: lead, customer, investor, partner, vendor, other
        status: active, inactive, churned, converted
        company_id: UUID of associated company
        title: Job title
        source: How we got this contact
        tags: List of tags
        data: Custom fields as dict

    Returns:
        Created contact
    """
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO crm.contacts (name, email, phone, type, status, company_id, title, source, tags, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            name, email, phone, type, status, company_id, title, source,
            tags or [], Json(data or {})
        )).fetchone()
        conn.commit()
    return dict(row)


def update_contact(contact_id: str, **kwargs) -> dict | None:
    """
    Update a contact.

    Args:
        contact_id: UUID of contact
        **kwargs: Fields to update (name, email, type, status, etc.)

    Returns:
        Updated contact
    """
    allowed = ['name', 'email', 'phone', 'type', 'status', 'company_id', 'title', 'source', 'source_detail', 'tags', 'data']
    updates = []
    params = []

    for key, value in kwargs.items():
        if key in allowed and value is not None:
            updates.append(f"{key} = %s")
            if key in ['data']:
                params.append(Json(value))
            else:
                params.append(value)

    if not updates:
        return get_contact(contact_id)

    updates.append("updated_at = %s")
    params.append(datetime.utcnow())
    params.append(contact_id)

    with get_connection() as conn:
        row = conn.execute(f"""
            UPDATE crm.contacts
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING *
        """, params).fetchone()
        conn.commit()

    return dict(row) if row else None


# === COMPANIES ===

def query_companies(
    type: str = None,
    search: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    Search companies by type or name/domain.

    Args:
        type: Filter by type (prospect, customer, partner, investor, vendor)
        search: Search in name or domain
        limit: Max results
    """
    conditions = []
    params = []

    if type:
        conditions.append("type = %s")
        params.append(type)
    if search:
        conditions.append("(name ILIKE %s OR domain ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT id, name, domain, industry, type, status, tags, created_at
            FROM crm.companies
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s
        """, params).fetchall()

    return [dict(r) for r in rows]


def create_company(
    name: str,
    domain: str = None,
    industry: str = None,
    size: str = None,
    type: str = "prospect",
    tags: list = None,
    data: dict = None,
) -> dict:
    """
    Create a new company.

    Args:
        name: Company name (required)
        domain: Website domain
        industry: Industry
        size: startup, smb, enterprise
        type: prospect, customer, partner, investor, vendor
        tags: List of tags
        data: Custom fields
    """
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO crm.companies (name, domain, industry, size, type, tags, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (name, domain, industry, size, type, tags or [], Json(data or {}))).fetchone()
        conn.commit()
    return dict(row)


# === INTERACTIONS ===

def log_interaction(
    type: str,
    contact_id: str = None,
    company_id: str = None,
    subject: str = None,
    content: str = None,
    direction: str = None,
    occurred_at: str = None,
    duration_minutes: int = None,
    event_id: str = None,
    data: dict = None,
) -> dict:
    """
    Log an interaction (meeting, call, email, note).

    Args:
        type: email, call, meeting, note, task
        contact_id: UUID of contact (optional)
        company_id: UUID of company (optional)
        subject: Subject/title
        content: Notes/content
        direction: inbound or outbound
        occurred_at: When it happened (ISO format, defaults to now)
        duration_minutes: Duration in minutes
        event_id: Link to events.events if applicable
        data: Additional data (attendees, outcomes, etc.)
    """
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO crm.interactions
            (type, contact_id, company_id, subject, content, direction, occurred_at, duration_minutes, event_id, data)
            VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), %s, %s, %s)
            RETURNING *
        """, (
            type, contact_id, company_id, subject, content, direction,
            occurred_at, duration_minutes, event_id, Json(data or {})
        )).fetchone()
        conn.commit()
    return dict(row)


def get_contact_interactions(contact_id: str, limit: int = 20) -> list[dict]:
    """Get recent interactions for a contact."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM crm.interactions
            WHERE contact_id = %s
            ORDER BY occurred_at DESC
            LIMIT %s
        """, (contact_id, limit)).fetchall()
    return [dict(r) for r in rows]


# Export tools for AI discovery
TOOLS = [
    query_contacts,
    get_contact,
    create_contact,
    update_contact,
    query_companies,
    create_company,
    log_interaction,
    get_contact_interactions,
]
