"""Tool discovery for chat agent."""
import importlib
from pathlib import Path
from typing import Callable

DOMAINS_PATH = Path(__file__).parent.parent.parent / "domains"


def discover_tools() -> list[Callable]:
    """Discover all tools from domain tools.py files."""
    tools = []

    for domain_dir in DOMAINS_PATH.iterdir():
        if domain_dir.is_dir():
            tools_file = domain_dir / "tools.py"
            if tools_file.exists():
                module_name = f"substrate.domains.{domain_dir.name}.tools"
                try:
                    module = importlib.import_module(module_name)
                    # Get all functions marked as tools
                    if hasattr(module, "TOOLS"):
                        tools.extend(module.TOOLS)
                except ImportError as e:
                    print(f"Warning: Could not load {module_name}: {e}")

    return tools
