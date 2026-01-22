"""MCP server exposing Substrate tools to Claude Code.

Run with: python -m substrate.ui.mcp.server
Or add to Claude Code: claude mcp add substrate -- python -m substrate.ui.mcp.server
"""
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import domain tools
from substrate.domains.notes.tools import (
    query_notes, get_note, create_note, update_note, delete_note
)
from substrate.domains.crm.tools import (
    query_contacts, get_contact, create_contact, update_contact,
    query_companies, create_company, log_interaction, get_contact_interactions
)
from substrate.domains.tasks.tools import (
    list_pending_tasks, query_tasks, get_task, create_task,
    update_task, complete_task, cancel_task
)
from substrate.domains.events.tools import (
    query_events, get_event, list_rules, create_rule,
    update_rule, delete_rule, reprocess_event, create_manual_event
)
from substrate.domains.auth.tools import (
    list_inboxes, get_inbox, create_inbox, add_inbox_member,
    remove_inbox_member, delete_inbox, list_users, get_user
)
from substrate.domains.email.tools import (
    send_email, list_emails, get_email, reply_to_email, get_email_stats
)
from substrate.domains.calendar.tools import (
    query_events as calendar_query_events,
    get_event as calendar_get_event,
    get_today_events, get_upcoming_events,
    create_event as calendar_create_event,
    update_event as calendar_update_event,
    cancel_event, delete_event as calendar_delete_event,
    add_attendee, update_attendee_status, remove_attendee
)

server = Server("substrate")


def _serialize(obj: Any) -> str:
    """Serialize result to JSON string."""
    def default(o):
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        if hasattr(o, '__dict__'):
            return o.__dict__
        return str(o)
    return json.dumps(obj, default=default, indent=2)


# ============== NOTES TOOLS ==============

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # Notes
        Tool(
            name="notes_query",
            description="Search notes by keyword or tag. Returns list of notes with id, title, tags, file_path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search in title/content"},
                    "tag": {"type": "string", "description": "Tag to filter by (e.g., '#work')"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10}
                }
            }
        ),
        Tool(
            name="notes_get",
            description="Get full note content by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "UUID of the note"}
                },
                "required": ["note_id"]
            }
        ),
        Tool(
            name="notes_create",
            description="Create a new note in the database and Obsidian vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Note title"},
                    "content": {"type": "string", "description": "Markdown content"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags like ['#work', '#ideas']"},
                    "frontmatter": {"type": "object", "description": "YAML frontmatter as dict"},
                    "folder": {"type": "string", "description": "Folder in vault (default: 'notes')", "default": "notes"}
                },
                "required": ["title", "content"]
            }
        ),
        Tool(
            name="notes_update",
            description="Update an existing note in database and vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "UUID of the note"},
                    "title": {"type": "string", "description": "New title"},
                    "content": {"type": "string", "description": "New content"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "New tags"},
                    "frontmatter": {"type": "object", "description": "Frontmatter to merge"}
                },
                "required": ["note_id"]
            }
        ),
        Tool(
            name="notes_delete",
            description="Delete a note from database (file stays in vault).",
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {"type": "string", "description": "UUID of the note"}
                },
                "required": ["note_id"]
            }
        ),

        # CRM - Contacts
        Tool(
            name="crm_contacts_query",
            description="Search contacts by type, status, company, or name/email.",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["lead", "customer", "investor", "partner", "vendor"], "description": "Filter by type"},
                    "status": {"type": "string", "enum": ["active", "inactive", "churned", "converted"], "description": "Filter by status"},
                    "company_id": {"type": "string", "description": "Filter by company UUID"},
                    "search": {"type": "string", "description": "Search in name or email"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="crm_contacts_get",
            description="Get full contact details by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "UUID of the contact"}
                },
                "required": ["contact_id"]
            }
        ),
        Tool(
            name="crm_contacts_create",
            description="Create a new contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact name"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "type": {"type": "string", "enum": ["lead", "customer", "investor", "partner", "vendor", "other"], "default": "lead"},
                    "status": {"type": "string", "enum": ["active", "inactive", "churned", "converted"], "default": "active"},
                    "company_id": {"type": "string", "description": "UUID of associated company"},
                    "title": {"type": "string", "description": "Job title"},
                    "source": {"type": "string", "description": "How we got this contact"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
                    "data": {"type": "object", "description": "Custom fields"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="crm_contacts_update",
            description="Update a contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "UUID of contact"},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "type": {"type": "string"},
                    "status": {"type": "string"},
                    "company_id": {"type": "string"},
                    "title": {"type": "string"},
                    "source": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "data": {"type": "object"}
                },
                "required": ["contact_id"]
            }
        ),

        # CRM - Companies
        Tool(
            name="crm_companies_query",
            description="Search companies by type or name/domain.",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["prospect", "customer", "partner", "investor", "vendor"], "description": "Filter by type"},
                    "search": {"type": "string", "description": "Search in name or domain"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="crm_companies_create",
            description="Create a new company.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Company name"},
                    "domain": {"type": "string", "description": "Website domain"},
                    "industry": {"type": "string", "description": "Industry"},
                    "size": {"type": "string", "enum": ["startup", "smb", "enterprise"], "description": "Company size"},
                    "type": {"type": "string", "enum": ["prospect", "customer", "partner", "investor", "vendor"], "default": "prospect"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "data": {"type": "object", "description": "Custom fields"}
                },
                "required": ["name"]
            }
        ),

        # CRM - Interactions
        Tool(
            name="crm_interactions_log",
            description="Log an interaction (meeting, call, email, note).",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["email", "call", "meeting", "note", "task"], "description": "Interaction type"},
                    "contact_id": {"type": "string", "description": "UUID of contact"},
                    "company_id": {"type": "string", "description": "UUID of company"},
                    "subject": {"type": "string", "description": "Subject/title"},
                    "content": {"type": "string", "description": "Notes/content"},
                    "direction": {"type": "string", "enum": ["inbound", "outbound"], "description": "Direction"},
                    "occurred_at": {"type": "string", "description": "When it happened (ISO format)"},
                    "duration_minutes": {"type": "integer", "description": "Duration in minutes"},
                    "data": {"type": "object", "description": "Additional data"}
                },
                "required": ["type"]
            }
        ),
        Tool(
            name="crm_interactions_get",
            description="Get recent interactions for a contact.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "UUID of the contact"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                },
                "required": ["contact_id"]
            }
        ),

        # Tasks
        Tool(
            name="tasks_pending",
            description="List pending tasks ordered by priority and due date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "description": "Filter by priority"},
                    "contact_id": {"type": "string", "description": "Filter by linked contact"},
                    "company_id": {"type": "string", "description": "Filter by linked company"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="tasks_query",
            description="Search all tasks by status, priority, or title.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "in_progress", "done", "cancelled"], "description": "Filter by status"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "description": "Filter by priority"},
                    "search": {"type": "string", "description": "Search in title"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="tasks_get",
            description="Get full task details by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID of the task"}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="tasks_create",
            description="Create a new task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task details"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"], "default": "medium"},
                    "due_at": {"type": "string", "description": "Due date (ISO format)"},
                    "contact_id": {"type": "string", "description": "Link to CRM contact"},
                    "company_id": {"type": "string", "description": "Link to CRM company"},
                    "assigned_to": {"type": "string", "description": "Who should do this"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "data": {"type": "object", "description": "Custom fields"}
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="tasks_update",
            description="Update a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID of task"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "done", "cancelled"]},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "due_at": {"type": "string"},
                    "contact_id": {"type": "string"},
                    "company_id": {"type": "string"},
                    "assigned_to": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "data": {"type": "object"}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="tasks_complete",
            description="Mark a task as done.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID of task"}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="tasks_cancel",
            description="Cancel a task.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "UUID of task"}
                },
                "required": ["task_id"]
            }
        ),

        # Events
        Tool(
            name="events_query",
            description="Search events by status, source, or sender.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "processed", "failed", "unmatched", "ignored"], "description": "Filter by status"},
                    "source": {"type": "string", "enum": ["email", "webhook", "manual"], "description": "Filter by source"},
                    "email_from": {"type": "string", "description": "Filter by sender email (partial match)"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="events_get",
            description="Get full event details by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of the event"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="events_rules_list",
            description="List all routing rules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "enabled_only": {"type": "boolean", "description": "Only return enabled rules", "default": True}
                }
            }
        ),
        Tool(
            name="events_rules_create",
            description="Create a new routing rule.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Rule name"},
                    "conditions": {"type": "object", "description": "Matching conditions (from_contains, subject_contains, etc.)"},
                    "action": {"type": "string", "enum": ["create_note", "tag", "ignore", "spawn_task"], "description": "Action to take"},
                    "action_config": {"type": "object", "description": "Action-specific config"},
                    "description": {"type": "string", "description": "Rule description"},
                    "priority": {"type": "integer", "description": "Higher = checked first", "default": 0}
                },
                "required": ["name", "conditions", "action"]
            }
        ),
        Tool(
            name="events_rules_update",
            description="Update an existing rule.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "UUID of the rule"},
                    "name": {"type": "string"},
                    "conditions": {"type": "object"},
                    "action": {"type": "string"},
                    "action_config": {"type": "object"},
                    "description": {"type": "string"},
                    "priority": {"type": "integer"},
                    "enabled": {"type": "boolean"}
                },
                "required": ["rule_id"]
            }
        ),
        Tool(
            name="events_rules_delete",
            description="Delete a rule.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "UUID of the rule"}
                },
                "required": ["rule_id"]
            }
        ),
        Tool(
            name="events_reprocess",
            description="Reprocess an event through the router.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of the event"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="events_create_manual",
            description="Create a manual event for testing rules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "description": "Type of event (e.g., 'email.received', 'test')"},
                    "payload": {"type": "object", "description": "Event payload data"},
                    "email_from": {"type": "string", "description": "Sender for email-like events"},
                    "email_to": {"type": "string", "description": "Recipient"},
                    "email_subject": {"type": "string", "description": "Subject"},
                    "email_body": {"type": "string", "description": "Body"}
                },
                "required": ["event_type", "payload"]
            }
        ),

        # Auth - Inboxes
        Tool(
            name="inboxes_list",
            description="List all email inboxes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "Filter to inboxes for this user"}
                }
            }
        ),
        Tool(
            name="inboxes_get",
            description="Get inbox details with members.",
            inputSchema={
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "UUID of the inbox"}
                },
                "required": ["inbox_id"]
            }
        ),
        Tool(
            name="inboxes_create",
            description="Create a new email inbox.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email address (e.g., 'hello@yourdomain.com')"},
                    "name": {"type": "string", "description": "Display name (e.g., 'Support Team')"},
                    "owner_id": {"type": "string", "description": "User UUID to add as owner"}
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="inboxes_add_member",
            description="Add a user to an inbox (for shared inboxes).",
            inputSchema={
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "UUID of the inbox"},
                    "user_id": {"type": "string", "description": "UUID of the user to add"},
                    "role": {"type": "string", "enum": ["owner", "member", "viewer"], "default": "member"}
                },
                "required": ["inbox_id", "user_id"]
            }
        ),
        Tool(
            name="inboxes_remove_member",
            description="Remove a user from an inbox.",
            inputSchema={
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "UUID of the inbox"},
                    "user_id": {"type": "string", "description": "UUID of the user to remove"}
                },
                "required": ["inbox_id", "user_id"]
            }
        ),
        Tool(
            name="inboxes_delete",
            description="Delete an inbox.",
            inputSchema={
                "type": "object",
                "properties": {
                    "inbox_id": {"type": "string", "description": "UUID of the inbox"}
                },
                "required": ["inbox_id"]
            }
        ),

        # Auth - Users
        Tool(
            name="users_list",
            description="List all users.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="users_get",
            description="Get user details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "UUID of the user"}
                },
                "required": ["user_id"]
            }
        ),

        # Email
        Tool(
            name="email_send",
            description="Send an email via Resend. IMPORTANT: First call without confirm to preview, then call with confirm=true to send.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email (or comma-separated list)"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body (HTML by default)"},
                    "html": {"type": "boolean", "description": "If true (default), body is HTML; if false, plain text", "default": True},
                    "from_email": {"type": "string", "description": "Sender (uses DEFAULT_FROM_EMAIL env var if not specified)"},
                    "reply_to": {"type": "string", "description": "Reply-to address"},
                    "confirm": {"type": "boolean", "description": "Set to true to actually send (required for sending)", "default": False}
                },
                "required": ["to", "subject", "body"]
            }
        ),
        Tool(
            name="email_list",
            description="List received emails.",
            inputSchema={
                "type": "object",
                "properties": {
                    "inbox": {"type": "string", "description": "Filter by inbox (e.g., 'support@yourdomain.com')"},
                    "from_address": {"type": "string", "description": "Filter by sender (partial match)"},
                    "search": {"type": "string", "description": "Search in subject or body"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="email_get",
            description="Get full email content by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "UUID of the email"}
                },
                "required": ["email_id"]
            }
        ),
        Tool(
            name="email_reply",
            description="Reply to a received email. IMPORTANT: First call without confirm to preview, then call with confirm=true to send.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "UUID of the email to reply to"},
                    "body": {"type": "string", "description": "Reply body (HTML by default)"},
                    "html": {"type": "boolean", "description": "If true (default), body is HTML", "default": True},
                    "confirm": {"type": "boolean", "description": "Set to true to actually send (required for sending)", "default": False}
                },
                "required": ["email_id", "body"]
            }
        ),
        Tool(
            name="email_stats",
            description="Get email statistics (counts by status, inbox, recent activity).",
            inputSchema={"type": "object", "properties": {}}
        ),

        # Calendar
        Tool(
            name="calendar_events_query",
            description="Search calendar events by date range, type, contact, or company.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start of date range (ISO format)"},
                    "end_date": {"type": "string", "description": "End of date range (ISO format)"},
                    "type": {"type": "string", "enum": ["meeting", "call", "reminder", "focus", "appointment"], "description": "Filter by type"},
                    "status": {"type": "string", "enum": ["tentative", "confirmed", "cancelled"], "description": "Filter by status"},
                    "contact_id": {"type": "string", "description": "Filter by linked contact"},
                    "company_id": {"type": "string", "description": "Filter by linked company"},
                    "search": {"type": "string", "description": "Search in title or description"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="calendar_events_get",
            description="Get full calendar event details by ID, including attendees.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of the event"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="calendar_today",
            description="Get today's calendar events.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="calendar_upcoming",
            description="Get upcoming calendar events (next N days).",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days to look ahead (default 7)", "default": 7},
                    "limit": {"type": "integer", "description": "Max results", "default": 20}
                }
            }
        ),
        Tool(
            name="calendar_events_create",
            description="Create a new calendar event with optional attendees.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "starts_at": {"type": "string", "description": "Start time (ISO format)"},
                    "ends_at": {"type": "string", "description": "End time (ISO format)"},
                    "type": {"type": "string", "enum": ["meeting", "call", "reminder", "focus", "appointment"], "default": "meeting"},
                    "status": {"type": "string", "enum": ["tentative", "confirmed", "cancelled"], "default": "confirmed"},
                    "description": {"type": "string", "description": "Event description"},
                    "location": {"type": "string", "description": "Physical address or video link"},
                    "all_day": {"type": "boolean", "description": "Is this an all-day event", "default": False},
                    "contact_id": {"type": "string", "description": "Link to primary CRM contact"},
                    "company_id": {"type": "string", "description": "Link to CRM company"},
                    "remind_before_minutes": {"type": "integer", "description": "Send reminder N minutes before (e.g., 15, 60)"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "data": {"type": "object", "description": "Custom fields (video_link, notes, etc.)"},
                    "attendees": {"type": "array", "items": {"type": "object"}, "description": "List of attendees with email, name, is_organizer, is_optional"}
                },
                "required": ["title", "starts_at", "ends_at"]
            }
        ),
        Tool(
            name="calendar_events_update",
            description="Update a calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of event"},
                    "title": {"type": "string"},
                    "starts_at": {"type": "string"},
                    "ends_at": {"type": "string"},
                    "type": {"type": "string"},
                    "status": {"type": "string"},
                    "description": {"type": "string"},
                    "location": {"type": "string"},
                    "all_day": {"type": "boolean"},
                    "contact_id": {"type": "string"},
                    "company_id": {"type": "string"},
                    "remind_before_minutes": {"type": "integer"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "data": {"type": "object"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="calendar_events_cancel",
            description="Cancel a calendar event (sets status to cancelled).",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of event"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="calendar_events_delete",
            description="Permanently delete a calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of event"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="calendar_attendees_add",
            description="Add an attendee to a calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of event"},
                    "email": {"type": "string", "description": "Attendee email"},
                    "name": {"type": "string", "description": "Attendee name"},
                    "contact_id": {"type": "string", "description": "Link to CRM contact"},
                    "is_organizer": {"type": "boolean", "default": False},
                    "is_optional": {"type": "boolean", "default": False}
                },
                "required": ["event_id", "email"]
            }
        ),
        Tool(
            name="calendar_attendees_update",
            description="Update an attendee's response status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of event"},
                    "email": {"type": "string", "description": "Attendee email"},
                    "status": {"type": "string", "enum": ["pending", "accepted", "declined", "tentative"], "description": "Response status"}
                },
                "required": ["event_id", "email", "status"]
            }
        ),
        Tool(
            name="calendar_attendees_remove",
            description="Remove an attendee from a calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "UUID of event"},
                    "email": {"type": "string", "description": "Attendee email"}
                },
                "required": ["event_id", "email"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    result = None

    # Notes
    if name == "notes_query":
        result = query_notes(
            query=arguments.get("query"),
            tag=arguments.get("tag"),
            limit=arguments.get("limit", 10)
        )
    elif name == "notes_get":
        result = get_note(arguments["note_id"])
    elif name == "notes_create":
        result = create_note(
            title=arguments["title"],
            content=arguments["content"],
            tags=arguments.get("tags"),
            frontmatter=arguments.get("frontmatter"),
            folder=arguments.get("folder", "notes")
        )
    elif name == "notes_update":
        result = update_note(
            note_id=arguments["note_id"],
            title=arguments.get("title"),
            content=arguments.get("content"),
            tags=arguments.get("tags"),
            frontmatter=arguments.get("frontmatter")
        )
    elif name == "notes_delete":
        result = delete_note(arguments["note_id"])

    # CRM - Contacts
    elif name == "crm_contacts_query":
        result = query_contacts(
            type=arguments.get("type"),
            status=arguments.get("status"),
            company_id=arguments.get("company_id"),
            search=arguments.get("search"),
            limit=arguments.get("limit", 20)
        )
    elif name == "crm_contacts_get":
        result = get_contact(arguments["contact_id"])
    elif name == "crm_contacts_create":
        result = create_contact(
            name=arguments["name"],
            email=arguments.get("email"),
            phone=arguments.get("phone"),
            type=arguments.get("type", "lead"),
            status=arguments.get("status", "active"),
            company_id=arguments.get("company_id"),
            title=arguments.get("title"),
            source=arguments.get("source"),
            tags=arguments.get("tags"),
            data=arguments.get("data")
        )
    elif name == "crm_contacts_update":
        contact_id = arguments.pop("contact_id")
        result = update_contact(contact_id, **arguments)

    # CRM - Companies
    elif name == "crm_companies_query":
        result = query_companies(
            type=arguments.get("type"),
            search=arguments.get("search"),
            limit=arguments.get("limit", 20)
        )
    elif name == "crm_companies_create":
        result = create_company(
            name=arguments["name"],
            domain=arguments.get("domain"),
            industry=arguments.get("industry"),
            size=arguments.get("size"),
            type=arguments.get("type", "prospect"),
            tags=arguments.get("tags"),
            data=arguments.get("data")
        )

    # CRM - Interactions
    elif name == "crm_interactions_log":
        result = log_interaction(
            type=arguments["type"],
            contact_id=arguments.get("contact_id"),
            company_id=arguments.get("company_id"),
            subject=arguments.get("subject"),
            content=arguments.get("content"),
            direction=arguments.get("direction"),
            occurred_at=arguments.get("occurred_at"),
            duration_minutes=arguments.get("duration_minutes"),
            data=arguments.get("data")
        )
    elif name == "crm_interactions_get":
        result = get_contact_interactions(
            contact_id=arguments["contact_id"],
            limit=arguments.get("limit", 20)
        )

    # Tasks
    elif name == "tasks_pending":
        result = list_pending_tasks(
            priority=arguments.get("priority"),
            contact_id=arguments.get("contact_id"),
            company_id=arguments.get("company_id"),
            limit=arguments.get("limit", 20)
        )
    elif name == "tasks_query":
        result = query_tasks(
            status=arguments.get("status"),
            priority=arguments.get("priority"),
            search=arguments.get("search"),
            limit=arguments.get("limit", 20)
        )
    elif name == "tasks_get":
        result = get_task(arguments["task_id"])
    elif name == "tasks_create":
        result = create_task(
            title=arguments["title"],
            description=arguments.get("description"),
            priority=arguments.get("priority", "medium"),
            due_at=arguments.get("due_at"),
            contact_id=arguments.get("contact_id"),
            company_id=arguments.get("company_id"),
            assigned_to=arguments.get("assigned_to"),
            tags=arguments.get("tags"),
            data=arguments.get("data")
        )
    elif name == "tasks_update":
        task_id = arguments.pop("task_id")
        result = update_task(task_id, **arguments)
    elif name == "tasks_complete":
        result = complete_task(arguments["task_id"])
    elif name == "tasks_cancel":
        result = cancel_task(arguments["task_id"])

    # Events
    elif name == "events_query":
        result = query_events(
            status=arguments.get("status"),
            source=arguments.get("source"),
            email_from=arguments.get("email_from"),
            limit=arguments.get("limit", 20)
        )
    elif name == "events_get":
        result = get_event(arguments["event_id"])
    elif name == "events_rules_list":
        result = list_rules(enabled_only=arguments.get("enabled_only", True))
    elif name == "events_rules_create":
        result = create_rule(
            name=arguments["name"],
            conditions=arguments["conditions"],
            action=arguments["action"],
            action_config=arguments.get("action_config"),
            description=arguments.get("description"),
            priority=arguments.get("priority", 0)
        )
    elif name == "events_rules_update":
        result = update_rule(
            rule_id=arguments["rule_id"],
            name=arguments.get("name"),
            conditions=arguments.get("conditions"),
            action=arguments.get("action"),
            action_config=arguments.get("action_config"),
            description=arguments.get("description"),
            priority=arguments.get("priority"),
            enabled=arguments.get("enabled")
        )
    elif name == "events_rules_delete":
        result = delete_rule(arguments["rule_id"])
    elif name == "events_reprocess":
        result = reprocess_event(arguments["event_id"])
    elif name == "events_create_manual":
        result = create_manual_event(
            event_type=arguments["event_type"],
            payload=arguments["payload"],
            email_from=arguments.get("email_from"),
            email_to=arguments.get("email_to"),
            email_subject=arguments.get("email_subject"),
            email_body=arguments.get("email_body")
        )

    # Inboxes
    elif name == "inboxes_list":
        result = list_inboxes(user_id=arguments.get("user_id"))
    elif name == "inboxes_get":
        result = get_inbox(arguments["inbox_id"])
    elif name == "inboxes_create":
        result = create_inbox(
            email=arguments["email"],
            name=arguments.get("name"),
            owner_id=arguments.get("owner_id")
        )
    elif name == "inboxes_add_member":
        result = add_inbox_member(
            inbox_id=arguments["inbox_id"],
            user_id=arguments["user_id"],
            role=arguments.get("role", "member")
        )
    elif name == "inboxes_remove_member":
        result = remove_inbox_member(
            inbox_id=arguments["inbox_id"],
            user_id=arguments["user_id"]
        )
    elif name == "inboxes_delete":
        result = delete_inbox(arguments["inbox_id"])

    # Users
    elif name == "users_list":
        result = list_users()
    elif name == "users_get":
        result = get_user(arguments["user_id"])

    # Email
    elif name == "email_send":
        result = send_email(
            to=arguments["to"],
            subject=arguments["subject"],
            body=arguments["body"],
            html=arguments.get("html", True),
            from_email=arguments.get("from_email"),
            reply_to=arguments.get("reply_to"),
            confirm=arguments.get("confirm", False)
        )
    elif name == "email_list":
        result = list_emails(
            inbox=arguments.get("inbox"),
            from_address=arguments.get("from_address"),
            search=arguments.get("search"),
            limit=arguments.get("limit", 20)
        )
    elif name == "email_get":
        result = get_email(arguments["email_id"])
    elif name == "email_reply":
        result = reply_to_email(
            email_id=arguments["email_id"],
            body=arguments["body"],
            html=arguments.get("html", True),
            confirm=arguments.get("confirm", False)
        )
    elif name == "email_stats":
        result = get_email_stats()

    # Calendar
    elif name == "calendar_events_query":
        result = calendar_query_events(
            start_date=arguments.get("start_date"),
            end_date=arguments.get("end_date"),
            type=arguments.get("type"),
            status=arguments.get("status"),
            contact_id=arguments.get("contact_id"),
            company_id=arguments.get("company_id"),
            search=arguments.get("search"),
            limit=arguments.get("limit", 20)
        )
    elif name == "calendar_events_get":
        result = calendar_get_event(arguments["event_id"])
    elif name == "calendar_today":
        result = get_today_events()
    elif name == "calendar_upcoming":
        result = get_upcoming_events(
            days=arguments.get("days", 7),
            limit=arguments.get("limit", 20)
        )
    elif name == "calendar_events_create":
        result = calendar_create_event(
            title=arguments["title"],
            starts_at=arguments["starts_at"],
            ends_at=arguments["ends_at"],
            type=arguments.get("type", "meeting"),
            status=arguments.get("status", "confirmed"),
            description=arguments.get("description"),
            location=arguments.get("location"),
            all_day=arguments.get("all_day", False),
            contact_id=arguments.get("contact_id"),
            company_id=arguments.get("company_id"),
            remind_before_minutes=arguments.get("remind_before_minutes"),
            tags=arguments.get("tags"),
            data=arguments.get("data"),
            attendees=arguments.get("attendees")
        )
    elif name == "calendar_events_update":
        event_id = arguments.pop("event_id")
        result = calendar_update_event(event_id, **arguments)
    elif name == "calendar_events_cancel":
        result = cancel_event(arguments["event_id"])
    elif name == "calendar_events_delete":
        result = calendar_delete_event(arguments["event_id"])
    elif name == "calendar_attendees_add":
        result = add_attendee(
            event_id=arguments["event_id"],
            email=arguments["email"],
            name=arguments.get("name"),
            contact_id=arguments.get("contact_id"),
            is_organizer=arguments.get("is_organizer", False),
            is_optional=arguments.get("is_optional", False)
        )
    elif name == "calendar_attendees_update":
        result = update_attendee_status(
            event_id=arguments["event_id"],
            email=arguments["email"],
            status=arguments["status"]
        )
    elif name == "calendar_attendees_remove":
        result = remove_attendee(
            event_id=arguments["event_id"],
            email=arguments["email"]
        )

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return [TextContent(type="text", text=_serialize(result))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
