# Substrate: Personal Business Operating System

## Purpose

A minimalist operating system for a solopreneur to rapidly build and integrate business systems. Instead of adopting rigid SaaS tools, Substrate lets you:

- **Spin up domains fast** - CRM, sales, invoicing, projects in hours not weeks
- **Own your data** - Everything in Postgres, queryable, exportable
- **Integrate anything** - Pull from Obsidian, HubSpot, Stripe, email, APIs
- **AI-native** - Chat interface to query, update, and automate across all domains
- **Automate with workflows** - Durable tasks via Absurd for syncing, reminders, pipelines

## Core Primitives

| Primitive | Technology | Purpose |
|-----------|------------|---------|
| **Database** | PostgreSQL | Single source of truth, one schema per domain |
| **Workflows** | Absurd | Durable background tasks, retries, scheduling |
| **Knowledge** | Obsidian | Documentation, notes, context (synced to DB) |
| **Interfaces** | FastAPI + Chat | CRUD APIs, dashboards, AI agent |

## Architecture

```
.
├── substrate/                  # Main codebase
│   ├── core/                   # Infrastructure primitives
│   │   ├── db/
│   │   │   ├── connection.py   # Connection pool, helpers
│   │   │   └── migrate.py      # Runs migrations for all domains
│   │   ├── worker/
│   │   │   ├── main.py         # Absurd worker loop
│   │   │   └── Dockerfile
│   │   └── config.py           # Environment, settings
│   │
│   ├── integrations/           # External data sources
│   │   ├── obsidian/
│   │   │   ├── sync.py         # Parse & index vault
│   │   │   └── tasks.py        # @task("obsidian.index")
│   │   ├── hubspot/
│   │   ├── stripe/
│   │   └── gmail/
│   │
│   ├── domains/                # Business logic by area
│   │   ├── crm/
│   │   │   ├── sql/001_init.sql
│   │   │   ├── logic.py
│   │   │   └── tasks.py
│   │   ├── sales/
│   │   ├── projects/
│   │   └── notes/              # Personal knowledge base
│   │
│   └── ui/                     # Interfaces (ways to interact)
│       ├── api/
│       │   ├── main.py         # Generic CRUD + domain routes
│       │   └── Dockerfile
│       ├── chat/
│       │   ├── agent.py        # AI chat interface
│       │   └── tools.py        # Loads tools from domains
│       ├── web/                # Dashboards (future)
│       └── cli/                # Command line tools (future)
│
├── config/
│   └── sql/
│       └── absurd.sql          # Absurd workflow engine schema
├── libs/
│   └── absurd-sdk/             # Vendored Absurd Python SDK
├── habitat/                    # Task monitoring dashboard
├── .secrets/                   # Deploy keys (gitignored)
├── vault/                      # Obsidian vault (symlink)
├── docker-compose.yml
├── pyproject.toml              # absurd-sdk from libs/
├── CLAUDE.md
└── DESIGN.md
```

## Layer Responsibilities

### core/
Infrastructure only. No business logic. Provides:
- Database connection pool and migration runner
- Worker process that discovers and runs tasks
- Shared configuration and environment handling

### integrations/
Connect to external systems. Each integration:
- Pulls data from external sources (APIs, files, webhooks)
- Pushes data out when needed
- Defines worker tasks for syncing

### domains/
Business logic organized by area. Each domain:
- Owns its database schema (`{domain}.` prefix)
- Contains pure business logic functions
- Defines worker tasks for automation
- Exposes AI tools for chat interface

### ui/
All human and AI interfaces:
- **api/** - REST endpoints, CRUD operations
- **chat/** - AI agent, natural language interface
- **web/** - Dashboards, admin panels
- **cli/** - Command line utilities

## Adding a New Domain

1. Create folder: `domains/{name}/`
2. Add schema: `domains/{name}/sql/001_init.sql`
3. Add logic: `domains/{name}/logic.py`
4. Add tasks: `domains/{name}/tasks.py` (optional)
5. Run migrations: `python -m core.db.migrate`

Example CRM domain:

```sql
-- domains/crm/sql/001_init.sql
CREATE SCHEMA IF NOT EXISTS crm;

CREATE TABLE crm.contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    name TEXT,
    company_id UUID,
    source TEXT,              -- 'hubspot', 'manual', 'website'
    data JSONB DEFAULT '{}',  -- flexible fields
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE crm.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    domain TEXT UNIQUE,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE crm.interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID REFERENCES crm.contacts(id),
    type TEXT,                -- 'email', 'call', 'meeting', 'note'
    content TEXT,
    occurred_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

```python
# domains/crm/logic.py
def enrich_contact(contact: dict) -> dict:
    """Add derived fields to contact."""
    # Business logic here
    return contact

def score_lead(contact: dict, interactions: list) -> int:
    """Calculate lead score based on activity."""
    score = 0
    # Scoring logic
    return score
```

```python
# domains/crm/tasks.py
from core.worker.registry import register_task

@register_task("crm.enrich")
def enrich_contact_task(ctx, contact_id: str):
    """Enrich contact with external data."""
    pass

@register_task("crm.sync-hubspot")
def sync_hubspot_task(ctx):
    """Pull contacts from HubSpot."""
    pass
```

## Adding an Integration

1. Create folder: `integrations/{name}/`
2. Add sync logic: `integrations/{name}/sync.py`
3. Add tasks: `integrations/{name}/tasks.py`

Integrations don't own schemas - they write to domain tables.

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                        EXTERNAL                              │
│  Obsidian    HubSpot    Stripe    Gmail    Webhooks         │
└──────┬─────────┬──────────┬─────────┬──────────┬────────────┘
       │         │          │         │          │
       ▼         ▼          ▼         ▼          ▼
┌─────────────────────────────────────────────────────────────┐
│                     integrations/                            │
│  obsidian/sync    hubspot/sync    stripe/sync    gmail/sync │
└──────┬─────────────────┬────────────────────────────────────┘
       │                 │
       ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                       domains/                               │
│     notes/          crm/          sales/        projects/   │
│   (notes.*)      (crm.*)       (sales.*)     (projects.*)   │
└──────┬─────────────────┬────────────────────────────────────┘
       │                 │
       ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      core/db                                 │
│                     PostgreSQL                               │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                         ui/                                  │
│      api/           chat/           web/          cli/      │
│   (REST/CRUD)    (AI agent)    (dashboards)   (commands)    │
└─────────────────────────────────────────────────────────────┘
```

## Conventions

### Database
- One schema per domain: `crm.*`, `sales.*`, `notes.*`
- Use `JSONB` for flexible/evolving fields
- Always include: `id`, `created_at`, `updated_at`
- Use `gen_random_uuid()` for IDs

### Tasks
- Name format: `{domain}.{action}` or `{integration}.{action}`
- Examples: `crm.enrich`, `obsidian.index`, `sales.update-pipeline`

### Files
- `sql/` - Numbered migrations: `001_init.sql`, `002_add_tags.sql`
- `logic.py` - Pure functions, no side effects
- `tasks.py` - Worker tasks, can have side effects
- `tools.py` - AI-callable functions (in domains only)

## Future Extensions

- **ui/web/** - SolidJS dashboards per domain
- **ui/cli/** - `substrate crm list-contacts`
- **integrations/calendar/** - Google Calendar sync
- **domains/invoicing/** - Stripe integration, invoice generation
