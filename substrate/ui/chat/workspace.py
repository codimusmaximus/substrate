"""Chat API with Pydantic AI and Workspace support."""

import json
import os
from dataclasses import dataclass
from typing import Any

import psycopg
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelMessage, ModelRequest, ModelResponse,
    UserPromptPart, TextPart, ToolCallPart, ToolReturnPart
)

from substrate.core.config import DATABASE_URL
from substrate.integrations.obsidian.writeback import write_note_to_file
from substrate.integrations.obsidian.git import git_commit_and_push
from substrate.domains.notes.embeddings import semantic_search, search_chunks

MODEL = os.getenv("PYDANTIC_AI_MODEL", "openai:gpt-4o")


@dataclass
class Deps:
    conn: psycopg.Connection
    workspace: list["WorkspaceItem"]


class WorkspaceItem(BaseModel):
    type: str  # 'table', 'json', 'text', 'markdown'
    title: str
    data: Any


class ChatResponse(BaseModel):
    message: str
    workspace: list[WorkspaceItem] = []


# Create agent with system prompt
agent = Agent(
    MODEL,
    deps_type=Deps,
    system_prompt="""You are a helpful assistant for managing a personal business system called Substrate.
You have access to a PostgreSQL database with notes stored in notes.notes table.

Schema:
- id: UUID primary key
- file_path: text (e.g., 'notes/my-note.md')
- title: text
- frontmatter: JSONB with type, status, area, etc.
- content: text (markdown)
- tags: text[] (e.g., ARRAY['#work', '#project'])
- created_at, updated_at: timestamps

Search tools:
- search_notes: Use for semantic/conceptual search (e.g., "notes about pricing strategy", "ideas for marketing")
- query_notes: Use for exact keyword/tag search (e.g., search for "#meeting" tag or "John" keyword)

When the user asks to find or show notes:
1. Use search_notes for conceptual queries, query_notes for exact matches
2. Use show_in_workspace to display the results

When creating new notes, use create_note then show the created note in workspace.
When updating existing notes, use update_note.

IMPORTANT: Always use show_in_workspace after retrieving data so the user can see it in the workspace panel.

Be concise in your text responses. Let the workspace show the data.""",
)


@agent.tool
async def query_notes(ctx: RunContext[Deps], search: str = "", tag: str = "", limit: int = 20) -> list[dict]:
    """Search notes by keyword or tag.

    Args:
        search: Text to search in title and content (optional)
        tag: Exact tag to filter by, e.g. '#work' (optional)
        limit: Max results to return
    """
    conditions = []
    params = []

    if search:
        conditions.append("(title ILIKE %s OR content ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    if tag:
        conditions.append("%s = ANY(tags)")
        params.append(tag)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)

    query = f"""
        SELECT id, title, file_path, frontmatter, tags,
               substring(content, 1, 200) as content_preview,
               created_at, updated_at
        FROM notes.notes
        {where}
        ORDER BY updated_at DESC
        LIMIT %s
    """

    rows = ctx.deps.conn.execute(query, params).fetchall()
    cols = ['id', 'title', 'file_path', 'frontmatter', 'tags', 'content_preview', 'created_at', 'updated_at']

    results = []
    for row in rows:
        d = dict(zip(cols, row))
        d['id'] = str(d['id'])
        d['created_at'] = d['created_at'].isoformat() if d['created_at'] else None
        d['updated_at'] = d['updated_at'].isoformat() if d['updated_at'] else None
        results.append(d)

    return results


@agent.tool
async def search_notes(ctx: RunContext[Deps], query: str, limit: int = 10) -> list[dict]:
    """Semantic search for notes by meaning/concept.

    Use this for conceptual queries like "notes about pricing", "marketing ideas", etc.
    Uses AI embeddings to find semantically similar passages within notes.

    Args:
        query: Natural language query describing what you're looking for
        limit: Max results to return (default 10)
    """
    # Try chunk search first (more granular)
    results = search_chunks(query, limit=limit)
    if results:
        return results
    # Fall back to whole-document search if no chunks
    return semantic_search(query, limit=limit)


@agent.tool
async def get_note(ctx: RunContext[Deps], note_id: str) -> dict | None:
    """Get full content of a note by ID."""
    row = ctx.deps.conn.execute(
        "SELECT * FROM notes.notes WHERE id = %s",
        (note_id,)
    ).fetchone()

    if not row:
        return None

    cols = [desc[0] for desc in ctx.deps.conn.execute("SELECT * FROM notes.notes LIMIT 0").description]
    d = dict(zip(cols, row))
    d['id'] = str(d['id'])
    for k in ['created_at', 'updated_at']:
        if d.get(k):
            d[k] = d[k].isoformat()
    return d


@agent.tool
async def create_note(
    ctx: RunContext[Deps],
    title: str,
    content: str,
    tags: list[str] = None,
    frontmatter: dict = None,
    folder: str = "notes",
) -> dict:
    """Create a new note in database and vault.

    Args:
        title: Note title
        content: Markdown content
        tags: List of tags like ['#work', '#ideas']
        frontmatter: YAML frontmatter dict (e.g., {"status": "draft"})
        folder: Folder in vault (default: "notes")
    """
    # Generate file path
    slug = title.lower().replace(" ", "-").replace("/", "-")
    for char in ["'", '"', "?", "!", ":", ";", "(", ")", "[", "]", "{", "}"]:
        slug = slug.replace(char, "")
    file_path = f"{folder}/{slug}.md"

    # Merge tags into frontmatter
    fm = frontmatter or {}
    if tags:
        fm["tags"] = [t.lstrip("#") for t in tags]

    tags = tags or []

    row = ctx.deps.conn.execute("""
        INSERT INTO notes.notes (file_path, title, content, frontmatter, tags)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, title, file_path, frontmatter, tags
    """, (file_path, title, content, json.dumps(fm), tags)).fetchone()

    ctx.deps.conn.commit()

    note = {
        "id": str(row[0]),
        "title": row[1],
        "file_path": row[2],
        "frontmatter": row[3],
        "tags": row[4],
        "content": content,
    }

    # Write to vault and push
    try:
        write_note_to_file(note)
        git_commit_and_push(f"Add: {title}")
        note["synced"] = True
    except Exception:
        note["synced"] = False

    return note


@agent.tool
async def update_note(
    ctx: RunContext[Deps],
    note_id: str,
    title: str = None,
    content: str = None,
    tags: list[str] = None,
    frontmatter: dict = None,
) -> dict | None:
    """Update an existing note.

    Args:
        note_id: The note ID to update
        title: New title (optional)
        content: New content (optional)
        tags: New tags list (optional)
        frontmatter: New frontmatter to merge (optional)
    """
    current = await get_note(ctx, note_id)
    if not current:
        return None

    updates = []
    params = []

    if title is not None:
        updates.append("title = %s")
        params.append(title)

    if content is not None:
        updates.append("content = %s")
        params.append(content)

    if tags is not None:
        updates.append("tags = %s")
        params.append(tags)

    if frontmatter is not None:
        fm = current.get('frontmatter', {}) or {}
        fm.update(frontmatter)
        updates.append("frontmatter = %s")
        params.append(json.dumps(fm))

    if not updates:
        return current

    updates.append("updated_at = NOW()")
    params.append(note_id)

    query = f"UPDATE notes.notes SET {', '.join(updates)} WHERE id = %s RETURNING *"
    row = ctx.deps.conn.execute(query, params).fetchone()
    ctx.deps.conn.commit()

    cols = [desc[0] for desc in ctx.deps.conn.execute("SELECT * FROM notes.notes LIMIT 0").description]
    note = dict(zip(cols, row))
    note['id'] = str(note['id'])

    # Write to vault and push
    try:
        write_note_to_file(note)
        git_commit_and_push(f"Update: {note['title']}")
        note["synced"] = True
    except Exception:
        note["synced"] = False

    return note


@agent.tool
async def list_tags(ctx: RunContext[Deps]) -> list[str]:
    """List all unique tags in use."""
    rows = ctx.deps.conn.execute(
        "SELECT DISTINCT unnest(tags) as tag FROM notes.notes ORDER BY tag"
    ).fetchall()
    return [r[0] for r in rows]


@agent.tool
async def show_in_workspace(ctx: RunContext[Deps], title: str, data: list[dict] | dict | str, display_type: str = "table") -> str:
    """Display data in the workspace panel for the user to see.

    Args:
        title: Title for the workspace section
        data: The data to display (list of dicts for table, dict for json, string for text/markdown)
        display_type: 'table', 'json', 'text', or 'markdown'
    """
    ctx.deps.workspace.append(WorkspaceItem(type=display_type, title=title, data=data))
    return f"Displayed '{title}' in workspace"


def build_message_history(history: list[dict]) -> list[ModelMessage]:
    """Convert simple dict history to ModelMessage objects."""
    messages: list[ModelMessage] = []
    for h in history:
        if h["role"] == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=h["content"])]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=h["content"])]))
    return messages


async def chat(message: str, history: list[dict] = None) -> ChatResponse:
    """Process a chat message and return response with workspace items."""
    workspace_items: list[WorkspaceItem] = []

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        deps = Deps(conn=conn, workspace=workspace_items)
        msg_history = build_message_history(history) if history else None
        result = await agent.run(message, deps=deps, message_history=msg_history)
        response_text = result.output if hasattr(result, 'output') else str(result)
        return ChatResponse(
            message=response_text,
            workspace=workspace_items
        )


async def chat_stream(message: str, history: list[dict] = None):
    """Stream chat response with tool calls and workspace items."""
    workspace_items: list[WorkspaceItem] = []
    seen_tool_calls: set[str] = set()

    try:
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            deps = Deps(conn=conn, workspace=workspace_items)
            msg_history = build_message_history(history) if history else None

            async with agent.run_stream(message, deps=deps, message_history=msg_history) as result:
                async for text in result.stream_text():
                    try:
                        for msg in result.all_messages():
                            if isinstance(msg, ModelResponse):
                                for part in msg.parts:
                                    if isinstance(part, ToolCallPart):
                                        call_id = part.tool_call_id or f"{part.tool_name}_{id(part)}"
                                        if call_id not in seen_tool_calls:
                                            seen_tool_calls.add(call_id)
                                            args = {}
                                            if hasattr(part.args, 'args_dict'):
                                                args = part.args.args_dict
                                            elif hasattr(part.args, 'args_json'):
                                                args = part.args.args_json
                                            else:
                                                args = str(part.args)
                                            yield {
                                                "type": "tool_call",
                                                "name": part.tool_name,
                                                "args": args
                                            }
                            elif isinstance(msg, ModelRequest):
                                for part in msg.parts:
                                    if isinstance(part, ToolReturnPart):
                                        call_id = part.tool_call_id or f"{part.tool_name}_{id(part)}"
                                        result_id = f"{call_id}_result"
                                        if result_id not in seen_tool_calls:
                                            seen_tool_calls.add(result_id)
                                            content = part.content
                                            if not isinstance(content, (str, int, float, bool)):
                                                content = str(content)[:500]
                                            yield {
                                                "type": "tool_result",
                                                "name": part.tool_name,
                                                "result": content
                                            }
                    except Exception:
                        pass

                    yield {"type": "text", "content": text}

            if workspace_items:
                yield {"type": "workspace", "items": [item.model_dump() for item in workspace_items]}
    except Exception as e:
        yield {"type": "error", "message": str(e)}
