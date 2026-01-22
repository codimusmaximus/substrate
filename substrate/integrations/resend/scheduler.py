"""Resend email sync scheduler.

Long-running task that periodically checks for new emails and processes them.
Runs on the 'email' queue to avoid blocking other tasks.
"""
import os

from substrate.core.worker.registry import register_task


# Scheduler configuration
SCHEDULER_CONFIG = {
    "task_name": "resend.scheduler",
    "queue": "email",
    "params": {
        "interval_seconds": int(os.getenv("EMAIL_POLL_INTERVAL", "60")),
    },
    "singleton": True,  # Only one instance should run
}


@register_task("resend.scheduler")
def resend_scheduler(params, ctx):
    """
    Long-running task that syncs emails every interval.

    Args:
        params: Dict with interval_seconds, max_interval_seconds
        ctx: Absurd task context
    """
    from substrate.integrations.resend.tasks import _do_sync

    interval_seconds = params.get("interval_seconds", 60)
    max_interval_seconds = params.get("max_interval_seconds", 3600)
    iteration = 0
    consecutive_errors = 0

    while True:
        iteration += 1
        result = ctx.step(f"sync-{iteration}", _do_sync)

        # Check for errors
        if result.get("error"):
            consecutive_errors += 1
            # Exponential backoff: base * 2^errors, capped at max
            backoff = min(interval_seconds * (2 ** consecutive_errors), max_interval_seconds)
            print(f"[resend.scheduler] Iteration {iteration}: error - {result['error']}, backing off {backoff}s")
            ctx.sleep_for(f"wait-{iteration}", backoff)
            continue

        # Success - reset error counter
        consecutive_errors = 0
        created = result.get("created", 0)
        processed = result.get("processed", 0)
        if created > 0:
            print(f"[resend.scheduler] Iteration {iteration}: synced {created} emails, {processed} processed")
        else:
            print(f"[resend.scheduler] Iteration {iteration}: no new emails")

        ctx.sleep_for(f"wait-{iteration}", interval_seconds)
