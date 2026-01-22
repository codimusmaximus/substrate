"""Auth domain tools - users and inboxes."""
from substrate.core.db.connection import get_connection


def list_inboxes(user_id: str = None) -> list[dict]:
    """
    List all inboxes, optionally filtered by user.

    Args:
        user_id: Filter to inboxes this user has access to
    """
    with get_connection() as conn:
        if user_id:
            rows = conn.execute("""
                SELECT i.id, i.email, i.name, i.created_at,
                       im.role, im.is_default,
                       (SELECT COUNT(*) FROM auth.inbox_members WHERE inbox_id = i.id) as member_count
                FROM auth.inboxes i
                JOIN auth.inbox_members im ON im.inbox_id = i.id
                WHERE im.user_id = %s
                ORDER BY im.is_default DESC, i.email
            """, (user_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT i.id, i.email, i.name, i.created_at,
                       (SELECT COUNT(*) FROM auth.inbox_members WHERE inbox_id = i.id) as member_count
                FROM auth.inboxes i
                ORDER BY i.email
            """).fetchall()
    return [dict(r) for r in rows]


def get_inbox(inbox_id: str) -> dict | None:
    """Get inbox details with members."""
    with get_connection() as conn:
        inbox = conn.execute(
            "SELECT * FROM auth.inboxes WHERE id = %s", (inbox_id,)
        ).fetchone()
        if not inbox:
            return None

        members = conn.execute("""
            SELECT u.id, u.email, u.name, im.role, im.is_default
            FROM auth.inbox_members im
            JOIN auth.users u ON u.id = im.user_id
            WHERE im.inbox_id = %s
        """, (inbox_id,)).fetchall()

        result = dict(inbox)
        result["members"] = [dict(m) for m in members]
        return result


def create_inbox(email: str, name: str = None, owner_id: str = None) -> dict:
    """
    Create a new inbox.

    Args:
        email: Email address for the inbox
        name: Display name
        owner_id: User to add as owner (optional)
    """
    with get_connection() as conn:
        row = conn.execute("""
            INSERT INTO auth.inboxes (email, name)
            VALUES (%s, %s)
            RETURNING *
        """, (email.lower(), name)).fetchone()

        inbox_id = row["id"]

        # Add owner if provided
        if owner_id:
            conn.execute("""
                INSERT INTO auth.inbox_members (inbox_id, user_id, role, is_default)
                VALUES (%s, %s, 'owner', true)
            """, (inbox_id, owner_id))

        conn.commit()
    return dict(row)


def add_inbox_member(inbox_id: str, user_id: str, role: str = "member") -> dict:
    """Add a user to an inbox."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO auth.inbox_members (inbox_id, user_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (inbox_id, user_id) DO UPDATE SET role = EXCLUDED.role
        """, (inbox_id, user_id, role))
        conn.commit()
    return {"success": True, "inbox_id": inbox_id, "user_id": user_id, "role": role}


def remove_inbox_member(inbox_id: str, user_id: str) -> dict:
    """Remove a user from an inbox."""
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM auth.inbox_members
            WHERE inbox_id = %s AND user_id = %s
        """, (inbox_id, user_id))
        conn.commit()
    return {"success": True}


def delete_inbox(inbox_id: str) -> dict:
    """Delete an inbox."""
    with get_connection() as conn:
        conn.execute("DELETE FROM auth.inboxes WHERE id = %s", (inbox_id,))
        conn.commit()
    return {"success": True}


def list_users() -> list[dict]:
    """List all users."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, email, name, created_at
            FROM auth.users
            ORDER BY name, email
        """).fetchall()
    return [dict(r) for r in rows]


def get_user(user_id: str) -> dict | None:
    """Get user details."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM auth.users WHERE id = %s", (user_id,)
        ).fetchone()
    return dict(row) if row else None
