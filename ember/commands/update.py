"""Slash command for updating the repo and rerunning the provisioner."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List

from ..slash_commands import SlashCommand, SlashCommandContext


def _run(label: str, command: List[str], cwd: Path) -> str:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    parts = [f"[{label}] exit {proc.returncode}"]
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(stderr)
    return "\n".join(parts)


def _handler(context: SlashCommandContext, _: List[str]) -> str:
    repo_root = Path(context.metadata.get("repo_root", Path(__file__).resolve().parent.parent))
    if not repo_root.exists():
        return f"[update] repo directory '{repo_root}' does not exist."

    logs: List[str] = []

    logs.append(_run("git fetch", ["git", "fetch", "--prune"], repo_root))
    logs.append(_run("git pull", ["git", "pull", "--ff-only"], repo_root))

    provision_cmd = ["./scripts/provision.sh"]
    sudo_path = shutil.which("sudo")
    if sudo_path:
        provision_cmd = [sudo_path, "-E"] + provision_cmd
    logs.append(_run("provision", provision_cmd, repo_root))

    return "\n\n".join(logs)


COMMAND = SlashCommand(
    name="update",
    description="Pull latest git changes and rerun the provisioner.",
    handler=_handler,
)
