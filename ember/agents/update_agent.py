"""Agent that summarizes repository update status."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shlex
import subprocess
from typing import Dict, List, Sequence

from ..configuration import ConfigurationBundle, Diagnostic, DEFAULT_UPDATE_BRANCHES

logger = logging.getLogger("ember.update")

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class UpdateSettings:
    enabled: bool
    allowed_branches: Sequence[str]
    fetch: bool

    @classmethod
    def from_bundle(cls, bundle: ConfigurationBundle) -> "UpdateSettings":
        raw = bundle.merged.get("update", {}) if bundle.merged else {}
        branches = raw.get("allowed_branches", DEFAULT_UPDATE_BRANCHES)
        if isinstance(branches, str):
            branches = [branches]
        allowed = [str(b).strip() for b in branches if str(b).strip()]
        if not allowed:
            allowed = list(DEFAULT_UPDATE_BRANCHES)
        return cls(
            enabled=bool(raw.get("enabled", False)),
            allowed_branches=tuple(allowed),
            fetch=bool(raw.get("fetch", False)),
        )


def run_update_agent(bundle: ConfigurationBundle) -> Dict[str, object]:
    settings = UpdateSettings.from_bundle(bundle)

    if not settings.enabled:
        detail = "update.agent disabled via configuration."
        logger.info(detail)
        return {"status": "skipped", "detail": detail}

    try:
        branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = _run_git(["rev-parse", "HEAD"])
        dirty = bool(_run_git(["status", "--porcelain"]))
    except FileNotFoundError:
        message = "git is not available; cannot inspect repo status."
        bundle.diagnostics.append(
            Diagnostic(level="error", message=message, source=REPO_ROOT)
        )
        logger.error(message)
        return {"status": "error", "detail": message}
    except subprocess.CalledProcessError as exc:
        message = f"git command failed: {' '.join(exc.cmd)}"
        bundle.diagnostics.append(
            Diagnostic(level="error", message=message, source=REPO_ROOT)
        )
        logger.error("update.agent git failure: %s", exc)
        return {"status": "error", "detail": message}

    fetch_detail = None
    if settings.fetch:
        try:
            fetch_output = _run_git(["fetch", "--dry-run"], allow_empty=True)
            fetch_detail = fetch_output or "(no changes)"
        except subprocess.CalledProcessError as exc:
            fetch_detail = f"fetch failed ({exc.returncode})"
            logger.warning("git fetch failed: %s", exc)

    status = "ok"
    detail_parts: List[str] = [f"branch={branch}", f"commit={commit[:7]}"]
    if dirty:
        status = "degraded"
        detail_parts.append("dirty=true")
    if branch not in settings.allowed_branches:
        status = "degraded"
        detail_parts.append("branch_not_allowed")
    if fetch_detail:
        detail_parts.append(f"fetch={fetch_detail}")

    detail = ", ".join(detail_parts)
    logger.info("update.agent completed: %s", detail)
    return {
        "status": status,
        "detail": detail,
        "branch": branch,
        "commit": commit,
        "dirty": dirty,
        "allowed_branches": list(settings.allowed_branches),
        "fetch_result": fetch_detail,
    }


def _run_git(args: Sequence[str], *, allow_empty: bool = False) -> str:
    cmd = ["git", *args]
    completed = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = completed.stdout.strip()
    if not output and not allow_empty:
        return ""
    return output


__all__ = ["run_update_agent", "UpdateSettings"]
