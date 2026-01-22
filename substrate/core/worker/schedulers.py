"""Scheduler discovery and management.

Discovers SCHEDULER_CONFIG from all domain/integration modules and
provides functions to spawn/manage long-running scheduler tasks.
"""
import importlib
from pathlib import Path
from typing import Any

from substrate.core.config import DATABASE_URL


def discover_schedulers() -> list[dict]:
    """
    Discover all scheduler configurations from domains and integrations.

    Looks for SCHEDULER_CONFIG in scheduler.py files.

    Returns:
        List of scheduler config dicts with task_name, queue, params, singleton
    """
    schedulers = []
    base_path = Path(__file__).parent.parent.parent

    # Check integrations
    integrations_path = base_path / "integrations"
    for int_dir in integrations_path.iterdir():
        if int_dir.is_dir():
            scheduler_file = int_dir / "scheduler.py"
            if scheduler_file.exists():
                module_name = f"substrate.integrations.{int_dir.name}.scheduler"
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, "SCHEDULER_CONFIG"):
                        config = module.SCHEDULER_CONFIG.copy()
                        config["module"] = module_name
                        schedulers.append(config)
                except ImportError as e:
                    print(f"Warning: Could not load scheduler {module_name}: {e}")

    # Check domains
    domains_path = base_path / "domains"
    for domain_dir in domains_path.iterdir():
        if domain_dir.is_dir():
            scheduler_file = domain_dir / "scheduler.py"
            if scheduler_file.exists():
                module_name = f"substrate.domains.{domain_dir.name}.scheduler"
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, "SCHEDULER_CONFIG"):
                        config = module.SCHEDULER_CONFIG.copy()
                        config["module"] = module_name
                        schedulers.append(config)
                except ImportError as e:
                    print(f"Warning: Could not load scheduler {module_name}: {e}")

    return schedulers


def get_running_schedulers() -> dict[str, Any]:
    """
    Get currently running scheduler tasks.

    Returns:
        Dict mapping task_name to task info
    """
    from substrate.core.db.connection import get_connection

    with get_connection() as conn:
        # Check all queue tables for running schedulers
        running = {}
        for queue in ["default", "obsidian", "email"]:
            try:
                rows = conn.execute(f"""
                    SELECT task_id, task_name, state, attempts
                    FROM absurd.t_{queue}
                    WHERE task_name LIKE '%%.scheduler'
                    AND state IN ('pending', 'running', 'sleeping')
                """).fetchall()
                for row in rows:
                    running[row["task_name"]] = dict(row)
            except Exception:
                # Queue might not exist yet
                pass

    return running


def spawn_scheduler(config: dict) -> dict:
    """
    Spawn a scheduler task if not already running.

    Args:
        config: Scheduler config with task_name, queue, params, singleton

    Returns:
        Result dict with spawned=True/False and details
    """
    from absurd_sdk import Absurd

    task_name = config["task_name"]
    queue = config.get("queue", "default")
    params = config.get("params", {})
    singleton = config.get("singleton", True)

    # Check if already running (for singleton schedulers)
    if singleton:
        running = get_running_schedulers()
        if task_name in running:
            return {
                "spawned": False,
                "reason": "already_running",
                "task_id": str(running[task_name].get("task_id")),
            }

    # Spawn the scheduler
    absurd = Absurd(DATABASE_URL, queue_name=queue)
    result = absurd.spawn(task_name, params, queue=queue)

    return {
        "spawned": True,
        "task_name": task_name,
        "queue": queue,
        "task_id": str(result.get("task_id")),
    }


def spawn_all_schedulers() -> list[dict]:
    """
    Discover and spawn all schedulers.

    Returns:
        List of spawn results
    """
    schedulers = discover_schedulers()
    results = []

    for config in schedulers:
        # Check if scheduler is enabled (defaults to True for backwards compatibility)
        if not config.get("enabled", True):
            print(f"[schedulers] {config['task_name']}: skipped (disabled)")
            results.append({
                "spawned": False,
                "reason": "disabled",
                "config": config,
            })
            continue

        result = spawn_scheduler(config)
        result["config"] = config
        results.append(result)
        print(f"[schedulers] {config['task_name']}: {result.get('reason', 'spawned')} on queue '{config.get('queue', 'default')}'")

    return results
