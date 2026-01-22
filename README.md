# Substrate

A personal business operating system framework. Build and integrate business systems (CRM, tasks, calendar, notes) with PostgreSQL, Python, and AI-native interfaces.

## Why Substrate?

Instead of adopting rigid SaaS tools, Substrate lets you:

- **Spin up domains fast** - CRM, sales, projects, invoicing in hours not weeks
- **Own your data** - Everything in PostgreSQL, queryable, exportable
- **Integrate anything** - Pull from Obsidian, APIs, webhooks, email
- **AI-native** - 70+ MCP tools for Claude Code integration
- **Automate with workflows** - Durable background tasks via Absurd

## Features

| Feature | Description |
|---------|-------------|
| **Domain-driven** | Modular business logic (CRM, Tasks, Calendar, Notes, Events) |
| **Generic CRUD API** | Auto-generated REST endpoints for all domain tables |
| **MCP Integration** | 70+ tools exposed to Claude Code for AI-powered workflows |
| **Background Tasks** | Durable task execution with retries via Absurd |
| **Two-way Sync** | Optional Obsidian vault sync for notes |
| **Web Dashboards** | Built-in CRUD browser, chat interface, calendar view |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/substrate.git
cd substrate/ai_second_brain

# Copy and configure environment
cp .env.template .env
# Edit .env with your settings (OPENAI_API_KEY required for AI features)

# Install dependencies
uv sync

# Start services and initialize database
make init
```

### Access Points

After setup, these services are available:

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:8000 | Main web interface |
| Chat | http://localhost:8000/chat | AI chat interface |
| Data Browser | http://localhost:8000/crud | Browse/edit all tables |
| Habitat | http://localhost:7890 | Task monitoring dashboard |
| PostgreSQL | localhost:5433 | Database (user: postgres, pass: postgres) |

## Architecture

```
substrate/
├── core/           # Infrastructure (db, worker, config)
├── integrations/   # External connectors (Obsidian, Resend)
├── domains/        # Business logic (CRM, Tasks, Calendar, Notes, Events, Auth, Email)
└── ui/             # Interfaces (API, Chat, MCP, Web)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Domains

| Domain | Description |
|--------|-------------|
| **auth** | Users, inboxes, shared inbox members |
| **calendar** | Events, attendees, reminders, .ics invites |
| **crm** | Contacts, companies, interactions |
| **email** | Email sending via Resend, received email management |
| **events** | Event routing rules, email pattern matching |
| **notes** | Knowledge base, Obsidian sync, embeddings |
| **tasks** | Task management with priority, due dates, CRM links |

## Claude Code Integration

Substrate exposes 70+ MCP tools for use with Claude Code:

```bash
# Add Substrate as an MCP server
claude mcp add substrate -- .venv/bin/python -m substrate.ui.mcp.server

# Verify it's connected
claude mcp list
```

Available tool categories:
- **Notes** - Query, create, update, delete notes
- **CRM** - Manage contacts, companies, interactions
- **Tasks** - Create and track tasks
- **Calendar** - Schedule events, manage attendees
- **Email** - Send emails, view inbox
- **Events** - Configure routing rules

## Development

```bash
# Run API locally (with hot reload)
make api

# Run worker locally
make worker

# Run database migrations
make migrate

# Access database shell
make db
```

## Configuration

All configuration is via environment variables. See [.env.template](.env.template) for all options.

### Required

- `DATABASE_URL` - PostgreSQL connection string

### Optional (for full features)

- `OPENAI_API_KEY` - For AI chat and embeddings
- `RESEND_API_KEY` - For email sending
- `VAULT_REPO` - For Obsidian vault git sync

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
