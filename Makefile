.PHONY: help up down logs migrate init dev api worker clean ps sync-notes sync-tasks sync

# Database connection for local commands
export DATABASE_URL ?= postgresql://postgres:postgres@localhost:5433/substrate

# Vault path (override with VAULT_PATH=/your/path)
export VAULT_PATH ?= ./vault

# Default target: show help
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Substrate - Personal Business Operating System"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  init          Full initialization (start services + migrate + queue)"
	@echo "  sync          Install/sync Python dependencies"
	@echo ""
	@echo "Services:"
	@echo "  up            Start all Docker services"
	@echo "  down          Stop all Docker services"
	@echo "  logs          View logs for all services"
	@echo "  ps            Show running containers"
	@echo ""
	@echo "Development:"
	@echo "  api           Run API locally with hot reload"
	@echo "  worker        Run background worker locally"
	@echo "  db            Open PostgreSQL shell"
	@echo "  migrate       Run database migrations"
	@echo ""
	@echo "Vault Sync (optional):"
	@echo "  sync-notes    Sync notes from vault to database"
	@echo "  sync-tasks    Sync tasks from vault to database"
	@echo "  embed         Generate embeddings for notes"
	@echo ""
	@echo "Maintenance:"
	@echo "  rebuild       Rebuild Docker containers"
	@echo "  clean         Remove all containers and volumes (WARNING: deletes data)"

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# View logs (all or specific service)
logs:
	docker compose logs -f

logs-%:
	docker compose logs -f $*

# Run database migrations
migrate:
	uv run python -m substrate.core.db.migrate

# Initialize absurd queue
init-queue:
	PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d substrate -c "SELECT absurd.create_queue('default')"

# Full initialization (start + migrate + queue)
init: up
	@echo "Waiting for postgres to be healthy..."
	@sleep 3
	$(MAKE) migrate
	$(MAKE) init-queue
	@echo "Done! Services available at:"
	@echo "  - Dashboard:    http://localhost:8000"
	@echo "  - Chat:         http://localhost:8000/chat"
	@echo "  - Data Browser: http://localhost:8000/crud"
	@echo "  - Habitat:      http://localhost:7890"
	@echo "  - Postgres:     localhost:5433"

# Run API locally (for development)
api:
	uv run uvicorn substrate.ui.api.main:app --reload

# Run worker locally (for development)
worker:
	uv run python -m substrate.core.worker.main

# Install/sync dependencies
sync:
	uv sync

# Database shell
db:
	PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d substrate

# Show running containers
ps:
	docker ps --filter "name=substrate" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Clean up everything (warning: deletes data)
clean:
	docker compose down -v
	rm -rf .venv

# Rebuild containers
rebuild:
	docker compose build --no-cache
	docker compose up -d

# Sync notes from vault to DB
sync-notes:
	uv run python -c "from substrate.integrations.obsidian.tasks import sync_vault; print(sync_vault('$(VAULT_PATH)'))"

# Sync tasks from vault's All Tasks.md to DB
sync-tasks:
	uv run python -m substrate.integrations.obsidian.task_sync $(VAULT_PATH)

# Sync everything (notes + tasks)
sync-all: sync-notes sync-tasks

# Generate embeddings for notes (requires OPENAI_API_KEY)
embed:
	uv run python -m substrate.domains.notes.embeddings update

# Full sync with embeddings
sync: sync-notes sync-tasks embed
