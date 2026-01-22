"""Substrate configuration.

All environment variables are loaded here and made available as module-level constants.
Required variables will raise errors on startup if not configured.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")

# =============================================================================
# CORE (Required)
# =============================================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/substrate"
)

# =============================================================================
# VAULT / NOTES (Optional - for Obsidian sync)
# =============================================================================

VAULT_PATH = os.getenv("VAULT_PATH", str(_project_root / "vault"))
VAULT_REPO = os.getenv("VAULT_REPO", "")  # GitHub repo URL for sync
VAULT_POLL_INTERVAL = int(os.getenv("VAULT_POLL_INTERVAL", "60"))

# =============================================================================
# AI (Optional - required for chat/embeddings)
# =============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PYDANTIC_AI_MODEL = os.getenv("PYDANTIC_AI_MODEL", "openai:gpt-4o")

# =============================================================================
# EMAIL (Optional - for Resend integration)
# =============================================================================

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
DEFAULT_FROM_NAME = os.getenv("DEFAULT_FROM_NAME", "Substrate")
EMAIL_POLL_INTERVAL = int(os.getenv("EMAIL_POLL_INTERVAL", "60"))

# =============================================================================
# FEATURE FLAGS
# =============================================================================

def is_vault_sync_enabled() -> bool:
    """Check if vault sync is configured and enabled."""
    return bool(VAULT_REPO)

def is_email_enabled() -> bool:
    """Check if email integration is configured."""
    return bool(RESEND_API_KEY)

def is_ai_enabled() -> bool:
    """Check if AI features are configured."""
    return bool(OPENAI_API_KEY)
