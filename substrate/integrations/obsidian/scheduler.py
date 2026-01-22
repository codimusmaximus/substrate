"""Obsidian vault sync scheduler.

Long-running task that periodically syncs the vault from git and indexes changes.
Runs on the 'obsidian' queue to avoid blocking other tasks.

This scheduler is OPTIONAL - it only runs if VAULT_REPO is configured.
"""
import os
import subprocess

from substrate.core.worker.registry import register_task
from substrate.core.config import VAULT_PATH, VAULT_REPO, VAULT_POLL_INTERVAL, is_vault_sync_enabled


# Scheduler configuration - only enabled if VAULT_REPO is set
SCHEDULER_CONFIG = {
    "task_name": "obsidian.scheduler",
    "queue": "obsidian",
    "params": {
        "interval_seconds": VAULT_POLL_INTERVAL,
    },
    "singleton": True,  # Only one instance should run
    "enabled": is_vault_sync_enabled(),  # Only run if vault sync is configured
}


def _git_pull_vault() -> dict:
    """Pull latest changes from vault git repo via SSH."""
    vault_repo = os.getenv("VAULT_REPO")

    if not vault_repo:
        return {"pulled": False, "reason": "VAULT_REPO not set"}

    # Convert HTTPS URL to SSH if needed
    if vault_repo.startswith("https://github.com/"):
        repo_path = vault_repo.replace("https://github.com/", "")
        if not repo_path.endswith(".git"):
            repo_path += ".git"
        ssh_url = f"git@github.com:{repo_path}"
    else:
        ssh_url = vault_repo

    # Fix SSH key permissions (mounted as read-only, needs 600)
    key_path = "/root/.ssh/id_ed25519"
    if os.path.exists(key_path):
        subprocess.run(["cp", key_path, "/tmp/deploy_key"], capture_output=True)
        subprocess.run(["chmod", "600", "/tmp/deploy_key"], capture_output=True)
        git_ssh_cmd = "ssh -i /tmp/deploy_key -o StrictHostKeyChecking=no"
    else:
        git_ssh_cmd = None

    env = os.environ.copy()
    if git_ssh_cmd:
        env["GIT_SSH_COMMAND"] = git_ssh_cmd

    # Clone if vault doesn't exist
    if not os.path.exists(os.path.join(VAULT_PATH, ".git")):
        print(f"[git] Cloning vault from {ssh_url}...")
        result = subprocess.run(
            ["git", "clone", ssh_url, VAULT_PATH],
            capture_output=True, text=True, env=env
        )
        if result.returncode != 0:
            return {"pulled": False, "error": result.stderr}
        return {"pulled": True, "action": "cloned"}

    # Pull if already cloned
    print(f"[git] Pulling vault updates...")
    result = subprocess.run(
        ["git", "-C", VAULT_PATH, "pull", "--ff-only"],
        capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        return {"pulled": False, "error": result.stderr}

    return {"pulled": True, "action": "pulled", "output": result.stdout.strip()}


@register_task("obsidian.scheduler")
def obsidian_scheduler(params, ctx):
    """
    Long-running task that syncs vault every interval.

    Args:
        params: Dict with interval_seconds
        ctx: Absurd task context
    """
    from substrate.integrations.obsidian.tasks import _do_sync

    interval_seconds = params.get("interval_seconds", 60)
    iteration = 0

    while True:
        iteration += 1

        # Pull from git first
        git_result = ctx.step(f"git-{iteration}", _git_pull_vault)

        # Only sync if git pull had changes (or first run)
        has_changes = git_result.get("output", "").strip() not in ["", "Already up to date."]

        if has_changes or iteration == 1:
            result = ctx.step(f"sync-{iteration}", lambda: _do_sync())
            print(f"[obsidian.scheduler] Iteration {iteration}: synced {result['indexed']} files, {result.get('changed', 0)} changed, {result.get('embedded', 0)} embedded")
        else:
            print(f"[obsidian.scheduler] Iteration {iteration}: no changes")

        ctx.sleep_for(f"wait-{iteration}", interval_seconds)
