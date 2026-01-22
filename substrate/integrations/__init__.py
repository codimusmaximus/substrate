"""Integration discovery."""
from pathlib import Path

INTEGRATIONS_PATH = Path(__file__).parent


def get_integrations() -> list[str]:
    """List all available integrations."""
    return [
        d.name for d in INTEGRATIONS_PATH.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]
