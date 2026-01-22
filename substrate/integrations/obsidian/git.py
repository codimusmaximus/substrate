"""Git operations for vault sync."""
import os
import subprocess
from substrate.core.config import VAULT_PATH


def _get_git_env() -> dict:
    """Get environment with SSH key configured."""
    env = os.environ.copy()

    key_path = "/root/.ssh/id_ed25519"
    if os.path.exists(key_path):
        # Copy key to fix permissions (mounted read-only)
        subprocess.run(["cp", key_path, "/tmp/deploy_key"], capture_output=True)
        subprocess.run(["chmod", "600", "/tmp/deploy_key"], capture_output=True)
        env["GIT_SSH_COMMAND"] = "ssh -i /tmp/deploy_key -o StrictHostKeyChecking=no"

    return env


def git_pull(vault_path: str = None) -> dict:
    """Pull latest changes from remote."""
    vault = vault_path or VAULT_PATH
    env = _get_git_env()

    result = subprocess.run(
        ["git", "-C", vault, "pull", "--ff-only"],
        capture_output=True, text=True, env=env
    )

    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    return {"success": True, "output": result.stdout.strip()}


def git_status(vault_path: str = None) -> dict:
    """Get git status of vault."""
    vault = vault_path or VAULT_PATH

    result = subprocess.run(
        ["git", "-C", vault, "status", "--porcelain"],
        capture_output=True, text=True
    )

    files = []
    for line in result.stdout.strip().split("\n"):
        if line:
            status = line[:2]
            path = line[3:]
            files.append({"status": status, "path": path})

    return {"changed": len(files) > 0, "files": files}


def git_commit(message: str, vault_path: str = None) -> dict:
    """Stage all changes and commit."""
    vault = vault_path or VAULT_PATH

    # Stage all changes
    result = subprocess.run(
        ["git", "-C", vault, "add", "-A"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    # Check if there's anything to commit
    status = git_status(vault_path)
    if not status["changed"]:
        return {"success": True, "committed": False, "reason": "nothing to commit"}

    # Commit
    result = subprocess.run(
        ["git", "-C", vault, "commit", "-m", message],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    return {"success": True, "committed": True, "output": result.stdout.strip()}


def git_push(vault_path: str = None) -> dict:
    """Push commits to remote."""
    vault = vault_path or VAULT_PATH
    env = _get_git_env()

    result = subprocess.run(
        ["git", "-C", vault, "push"],
        capture_output=True, text=True, env=env
    )

    if result.returncode != 0:
        return {"success": False, "error": result.stderr}

    return {"success": True, "output": result.stdout.strip() or result.stderr.strip()}


def git_commit_and_push(message: str, vault_path: str = None) -> dict:
    """Commit all changes and push to remote."""
    commit_result = git_commit(message, vault_path)
    if not commit_result.get("success"):
        return commit_result

    if not commit_result.get("committed"):
        return {"success": True, "pushed": False, "reason": "nothing to push"}

    push_result = git_push(vault_path)
    if not push_result.get("success"):
        return {"success": False, "committed": True, "push_error": push_result.get("error")}

    return {"success": True, "committed": True, "pushed": True}
