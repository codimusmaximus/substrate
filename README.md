<p align="center">
  <img src="docs/assets/logo-dark.svg" alt="Substrate" width="350">
</p>

<p align="center">
  <strong>Your personal business operating system.</strong><br>
  Build modular business systems with PostgreSQL, Python, and AI-native interfaces.
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP%20Tools-70+-green.svg" alt="MCP Tools"></a>
</p>

---

## The Problem

You're running a business with 10+ SaaS subscriptions. Your data is scattered across tools that don't integrate. You can't query across systems. You don't own anything.

## The Solution

**Substrate** gives you the primitives to build exactly what you need—then extend it with your own modules.

<p align="center">
  <img src="docs/assets/architecture.svg" alt="Substrate Architecture" width="100%">
</p>

---

## Modular By Design

Every feature in Substrate is a **self-contained module**. CRM, Tasks, Calendar—they're all just modules in the `domains/` folder. You can add your own in minutes.

<p align="center">
  <img src="docs/assets/modules.svg" alt="Build Your Own Modules" width="100%">
</p>

### Create a Module in 4 Steps

```bash
# 1. Create the folder
mkdir -p substrate/domains/invoicing/sql
```

```sql
-- 2. Define schema: sql/001_init.sql
CREATE SCHEMA IF NOT EXISTS invoicing;

CREATE TABLE invoicing.invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID REFERENCES crm.contacts(id),
    status TEXT DEFAULT 'draft',
    total_cents INTEGER,
    due_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

```python
# 3. Add AI tools: tools.py
def create_invoice(contact_id: str, amount: int) -> dict:
    """Create an invoice for a contact."""
    # Your business logic here
    pass
```

```bash
# 4. Run migrations
make migrate
```

**That's it.** Your module now has:
- REST API endpoints (`/api/invoicing/invoices`)
- Web UI for browsing/editing
- MCP tools for Claude Code
- Background task support

---

## How It Works

<p align="center">
  <img src="docs/assets/dataflow.svg" alt="Data Flow" width="100%">
</p>

Ask Claude naturally. Substrate handles the rest.

```
You: "Create a task to follow up with John next week"

Claude → MCP Server → PostgreSQL → Done

You: "What invoices are overdue?"

Claude → MCP Server → PostgreSQL → "You have 3 overdue invoices..."
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/codimusmaximus/substrate.git
cd substrate

# Configure
cp .env.template .env
# Add your OPENAI_API_KEY

# Launch
uv sync && make init
```

Open http://localhost:8000 — you're running.

| Endpoint | Purpose |
|----------|---------|
| [localhost:8000](http://localhost:8000) | Dashboard |
| [localhost:8000/chat](http://localhost:8000/chat) | AI Chat |
| [localhost:8000/crud](http://localhost:8000/crud) | Data Browser |
| [localhost:7890](http://localhost:7890) | Task Monitor |

---

## Built-in Modules

| Module | Description | AI Tools |
|--------|-------------|----------|
| **crm/** | Contacts, companies, interactions | `crm_contacts_*`, `crm_companies_*` |
| **tasks/** | Task management with priorities | `tasks_create`, `tasks_complete`, ... |
| **calendar/** | Events, attendees, reminders | `calendar_today`, `calendar_upcoming`, ... |
| **notes/** | Knowledge base, embeddings | `notes_query`, `notes_create`, ... |
| **email/** | Send/receive via Resend | `email_send`, `email_list`, ... |
| **events/** | Routing rules, webhooks | `events_rules_*`, `events_query` |
| **auth/** | Users and inboxes | `inboxes_*`, `users_*` |

---

## Claude Code Integration

Substrate exposes **70+ MCP tools** for Claude Code:

```bash
claude mcp add substrate -- .venv/bin/python -m substrate.ui.mcp.server
```

Then just ask:

```
"Show me contacts I haven't talked to in 30 days"
"Create a meeting with John for tomorrow at 2pm"
"Draft a follow-up email for the Acme deal"
"What tasks are due this week?"
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Database** | PostgreSQL + pgvector | Data + vector embeddings |
| **Workflows** | Absurd | Durable background tasks |
| **API** | FastAPI | REST endpoints |
| **AI** | Pydantic AI + OpenAI | Chat interface |
| **MCP** | Model Context Protocol | Claude Code integration |
| **Monitoring** | Habitat | Task dashboard (Go + SolidJS) |

---

## Project Structure

```
substrate/
├── core/                   # Infrastructure (don't modify)
│   ├── db/                 # Connection pool, migrations
│   ├── worker/             # Background task runner
│   └── config.py           # Environment configuration
│
├── domains/                # ← YOUR MODULES GO HERE
│   ├── crm/                # Contacts, companies
│   ├── tasks/              # Task management
│   ├── calendar/           # Events, scheduling
│   ├── notes/              # Knowledge base
│   ├── email/              # Email integration
│   ├── events/             # Routing rules
│   ├── auth/               # Users, inboxes
│   └── your-module/        # ← Add your own!
│
├── integrations/           # External system connectors
│   ├── obsidian/           # Vault sync (optional)
│   └── resend/             # Email API
│
└── ui/                     # Interfaces
    ├── api/                # REST API
    ├── chat/               # AI chat
    ├── mcp/                # Claude Code server
    └── web/                # Dashboards
```

---

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection |
| `OPENAI_API_KEY` | For AI | Chat and embeddings |
| `RESEND_API_KEY` | For email | Send emails |
| `VAULT_REPO` | For sync | Obsidian git sync |

See [.env.template](.env.template) for all options.

---

## Development

```bash
make help          # Show all commands
make api           # Run API with hot reload
make worker        # Run background worker
make db            # PostgreSQL shell
make migrate       # Run migrations
```

---

## Philosophy

> **Manual first.** Do it by hand until you understand it.
>
> **Then systematize.** Create tables and workflows when the pattern is clear.
>
> **Then augment.** Add AI tools when intelligence would help.
>
> **Then automate.** Schedule agents when you trust the process.

Read the full [Architecture Guide](docs/ARCHITECTURE.md).

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT License - see [LICENSE](LICENSE).

---

<p align="center">
  <sub>Built for people who want to own their stack.</sub>
</p>
