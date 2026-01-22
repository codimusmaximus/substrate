"""Task registry for worker."""
from typing import Callable
from functools import wraps

_tasks: dict[str, Callable] = {}


def register_task(name: str):
    """Decorator to register a task."""
    def decorator(fn: Callable) -> Callable:
        _tasks[name] = fn
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_tasks() -> dict[str, Callable]:
    """Get all registered tasks."""
    return _tasks.copy()


def discover_tasks():
    """Import all task modules to register them."""
    import importlib
    from pathlib import Path

    # Discover domain tasks
    domains_path = Path(__file__).parent.parent.parent / "domains"
    for domain_dir in domains_path.iterdir():
        if domain_dir.is_dir():
            tasks_file = domain_dir / "tasks.py"
            if tasks_file.exists():
                module_name = f"substrate.domains.{domain_dir.name}.tasks"
                try:
                    importlib.import_module(module_name)
                except ImportError as e:
                    print(f"Warning: Could not load {module_name}: {e}")

    # Discover integration tasks
    integrations_path = Path(__file__).parent.parent.parent / "integrations"
    for int_dir in integrations_path.iterdir():
        if int_dir.is_dir():
            tasks_file = int_dir / "tasks.py"
            if tasks_file.exists():
                module_name = f"substrate.integrations.{int_dir.name}.tasks"
                try:
                    importlib.import_module(module_name)
                except ImportError as e:
                    print(f"Warning: Could not load {module_name}: {e}")
