"""Generic CRUD API for all domains."""
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row

from substrate.core.config import DATABASE_URL
from substrate.domains import get_domains

app = FastAPI(title="Substrate API")

# Serve web UI
WEB_DIR = Path(__file__).parent.parent / "web"
STATIC_DIR = os.getenv("STATIC_DIR", str(WEB_DIR / "dist"))

# Mount static files (CSS, JS, etc.)
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


# Chat endpoints
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class WorkspaceItemModel(BaseModel):
    type: str
    title: str
    data: Any


class ChatResponseModel(BaseModel):
    message: str
    workspace: list[WorkspaceItemModel] = []


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponseModel:
    """Chat with the AI assistant."""
    from substrate.ui.chat.workspace import chat
    result = await chat(request.message, request.history)
    return result


@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """Stream chat response using Server-Sent Events."""
    from substrate.ui.chat.workspace import chat_stream

    async def event_generator():
        async for event in chat_stream(request.message, request.history):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@app.get("/api/calendar/upcoming")
def calendar_upcoming(days: int = 7):
    """Get upcoming calendar events with attendees."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days)

    with get_conn() as conn:
        # Get events in date range
        events = conn.execute("""
            SELECT * FROM calendar.events
            WHERE starts_at >= %s AND starts_at < %s
            ORDER BY starts_at ASC
        """, (now, end_date)).fetchall()

        # Get attendees for all events
        if events:
            event_ids = [str(e["id"]) for e in events]
            attendees = conn.execute("""
                SELECT * FROM calendar.attendees
                WHERE event_id = ANY(%s)
            """, (event_ids,)).fetchall()

            # Group attendees by event
            attendees_by_event = {}
            for att in attendees:
                eid = str(att["event_id"])
                if eid not in attendees_by_event:
                    attendees_by_event[eid] = []
                attendees_by_event[eid].append(att)

            # Attach attendees to events
            for event in events:
                event["attendees"] = attendees_by_event.get(str(event["id"]), [])
        else:
            events = []

    return {"events": events}


@app.get("/api/calendar/today")
def calendar_today():
    """Get today's calendar events with attendees."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    with get_conn() as conn:
        events = conn.execute("""
            SELECT * FROM calendar.events
            WHERE starts_at >= %s AND starts_at < %s
            ORDER BY starts_at ASC
        """, (start_of_day, end_of_day)).fetchall()

        if events:
            event_ids = [str(e["id"]) for e in events]
            attendees = conn.execute("""
                SELECT * FROM calendar.attendees
                WHERE event_id = ANY(%s)
            """, (event_ids,)).fetchall()

            attendees_by_event = {}
            for att in attendees:
                eid = str(att["event_id"])
                if eid not in attendees_by_event:
                    attendees_by_event[eid] = []
                attendees_by_event[eid].append(att)

            for event in events:
                event["attendees"] = attendees_by_event.get(str(event["id"]), [])

    return {"events": events}


@app.get("/api/domains")
def list_domains():
    """List available domains."""
    return {"domains": get_domains()}


@app.get("/api/{schema}/tables")
def list_tables(schema: str):
    """List tables in a schema."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
        """, (schema,)).fetchall()
    return {"tables": [r["table_name"] for r in rows]}


@app.get("/api/{schema}/{table}")
def list_rows(schema: str, table: str, limit: int = 100, offset: int = 0):
    """List rows from a table."""
    with get_conn() as conn:
        # Validate schema.table exists
        rows = conn.execute(
            f'SELECT * FROM "{schema}"."{table}" LIMIT %s OFFSET %s',
            (limit, offset)
        ).fetchall()
    return {"rows": rows}


@app.get("/api/{schema}/{table}/{id}")
def get_row(schema: str, table: str, id: str):
    """Get a single row by ID."""
    with get_conn() as conn:
        row = conn.execute(
            f'SELECT * FROM "{schema}"."{table}" WHERE id = %s',
            (id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@app.post("/api/{schema}/{table}")
def create_row(schema: str, table: str, data: dict):
    """Create a new row."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f"%({k})s" for k in data.keys())

    with get_conn() as conn:
        row = conn.execute(
            f'INSERT INTO "{schema}"."{table}" ({columns}) VALUES ({placeholders}) RETURNING *',
            data
        ).fetchone()
        conn.commit()
    return row


@app.patch("/api/{schema}/{table}/{id}")
def update_row(schema: str, table: str, id: str, data: dict):
    """Update a row."""
    set_clause = ", ".join(f"{k} = %({k})s" for k in data.keys())
    data["id"] = id

    with get_conn() as conn:
        row = conn.execute(
            f'UPDATE "{schema}"."{table}" SET {set_clause} WHERE id = %(id)s RETURNING *',
            data
        ).fetchone()
        conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@app.delete("/api/{schema}/{table}/{id}")
def delete_row(schema: str, table: str, id: str):
    """Delete a row."""
    with get_conn() as conn:
        conn.execute(f'DELETE FROM "{schema}"."{table}" WHERE id = %s', (id,))
        conn.commit()
    return {"deleted": True}


# Serve web UI pages
@app.get("/")
async def index():
    """Serve the dashboard as landing page."""
    return HTMLResponse((WEB_DIR / "dashboard.html").read_text())

@app.get("/chat")
async def chat_ui():
    """Serve the chat UI."""
    return HTMLResponse((WEB_DIR / "chat.html").read_text())

@app.get("/crud")
async def crud_ui():
    """Serve the CRUD UI."""
    return HTMLResponse((WEB_DIR / "crud.html").read_text())

@app.get("/kanban")
async def kanban_ui():
    """Serve the Kanban board."""
    return HTMLResponse((WEB_DIR / "kanban.html").read_text())

@app.get("/cards")
async def cards_ui():
    """Serve the Cards view."""
    return HTMLResponse((WEB_DIR / "cards.html").read_text())

@app.get("/calendar")
async def calendar_ui():
    """Serve the Calendar view."""
    return HTMLResponse((WEB_DIR / "calendar.html").read_text())
