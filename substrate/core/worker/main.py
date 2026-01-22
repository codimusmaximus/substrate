"""Absurd worker that runs tasks from all domains.

Supports multiple queues running in parallel:
- default: One-off tasks (invites, responses, etc.)
- obsidian: Vault sync scheduler
- email: Email sync scheduler
"""
import os
import threading
from absurd_sdk import Absurd

from ..config import DATABASE_URL

# Queues to process
QUEUES = ["default", "obsidian", "email"]


def create_worker(queue_name: str) -> Absurd:
    """Create and configure an Absurd worker for a specific queue."""
    absurd = Absurd(DATABASE_URL, queue_name=queue_name)

    # Discover and register all domain/integration tasks
    from substrate.core.worker.registry import discover_tasks, get_tasks
    discover_tasks()
    for task_name, task_fn in get_tasks().items():
        absurd.register_task(task_name)(task_fn)

    # Also discover scheduler tasks (they use @register_task decorator)
    from substrate.core.worker.schedulers import discover_schedulers
    discover_schedulers()  # This imports the modules which registers tasks

    # Re-register after scheduler discovery
    for task_name, task_fn in get_tasks().items():
        if task_name not in absurd._registry:
            absurd.register_task(task_name)(task_fn)

    return absurd


def run_worker(queue_name: str):
    """Run a worker for a specific queue (blocking)."""
    print(f"[worker:{queue_name}] Starting...")
    absurd = create_worker(queue_name)
    print(f"[worker:{queue_name}] Registered {len(absurd._registry)} tasks")
    absurd.start_worker()


def main():
    """Run workers for all queues in parallel threads."""
    print("Starting Substrate worker...")
    print(f"Queues: {QUEUES}")

    # Spawn schedulers first
    from substrate.core.worker.schedulers import spawn_all_schedulers
    print("\n[startup] Spawning schedulers...")
    spawn_all_schedulers()

    # Start a worker thread for each queue
    threads = []
    for queue_name in QUEUES:
        thread = threading.Thread(
            target=run_worker,
            args=(queue_name,),
            name=f"worker-{queue_name}",
            daemon=True,
        )
        threads.append(thread)
        thread.start()

    print(f"\n[startup] Started {len(threads)} worker threads")

    # Keep main thread alive
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\n[shutdown] Stopping workers...")


if __name__ == "__main__":
    main()
