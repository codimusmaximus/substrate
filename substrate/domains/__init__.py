"""Domain discovery."""
from pathlib import Path

DOMAINS_PATH = Path(__file__).parent


def get_domains() -> list[str]:
    """List all available domains."""
    return [
        d.name for d in DOMAINS_PATH.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    ]
