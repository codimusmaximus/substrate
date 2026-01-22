# Contributing to Substrate

Thank you for your interest in contributing to Substrate! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- [uv](https://github.com/astral-sh/uv) for Python package management
- Git

### Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/your-username/substrate.git
   cd substrate/ai_second_brain
   ```

2. **Set up environment**
   ```bash
   cp .env.template .env
   # Edit .env with your settings
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Start services**
   ```bash
   make init
   ```

5. **Verify setup**
   - API: http://localhost:8000
   - Database: `make db`

## Project Structure

```
substrate/
├── core/           # Infrastructure (don't add business logic here)
│   ├── db/         # Database connection, migrations
│   ├── worker/     # Background task runner
│   └── config.py   # Environment configuration
├── integrations/   # External system connectors
│   ├── obsidian/   # Obsidian vault sync
│   └── resend/     # Email via Resend API
├── domains/        # Business logic (add new features here)
│   ├── auth/       # Users, inboxes
│   ├── calendar/   # Events, attendees
│   ├── crm/        # Contacts, companies
│   └── ...
└── ui/             # User interfaces
    ├── api/        # REST API (FastAPI)
    ├── chat/       # AI chat agent
    ├── mcp/        # Claude Code MCP server
    └── web/        # Web dashboards
```

## Adding a New Domain

1. Create the domain folder:
   ```bash
   mkdir -p substrate/domains/myfeature/sql
   ```

2. Add database schema (`sql/001_init.sql`):
   ```sql
   CREATE SCHEMA IF NOT EXISTS myfeature;

   CREATE TABLE myfeature.items (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       name TEXT NOT NULL,
       data JSONB DEFAULT '{}',
       created_at TIMESTAMPTZ DEFAULT now(),
       updated_at TIMESTAMPTZ DEFAULT now()
   );
   ```

3. Add business logic (`logic.py`):
   ```python
   from substrate.core.db.connection import get_connection

   def create_item(name: str, data: dict = None) -> dict:
       with get_connection() as conn:
           row = conn.execute(
               "INSERT INTO myfeature.items (name, data) VALUES (%s, %s) RETURNING *",
               (name, data or {})
           ).fetchone()
       return dict(row)
   ```

4. Add AI tools (`tools.py`) - optional:
   ```python
   def create_item_tool(name: str, data: dict = None) -> dict:
       """Create a new item."""
       from .logic import create_item
       return create_item(name, data)
   ```

5. Run migrations:
   ```bash
   make migrate
   ```

## Adding MCP Tools

To expose a new tool to Claude Code:

1. Add the tool function to your domain's `tools.py`
2. Register it in `substrate/ui/mcp/server.py`:
   - Add to the imports
   - Add Tool definition in `list_tools()`
   - Add handler in `call_tool()`

## Code Style

- Use type hints for function parameters and return values
- Keep functions small and focused
- Business logic goes in `logic.py`, side effects in `tasks.py`
- Use the existing patterns in the codebase as reference

## Testing

```bash
# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_crm.py
```

## Making Changes

1. Create a branch for your changes:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes and test them locally

3. Commit with a clear message:
   ```bash
   git commit -m "Add: new feature for X"
   ```

4. Push and create a pull request

## Pull Request Guidelines

- Keep PRs focused on a single change
- Include a clear description of what and why
- Update documentation if adding new features
- Add tests for new functionality when possible

## Questions?

Open an issue for questions, bug reports, or feature requests.
