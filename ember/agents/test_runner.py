"""Agent that runs the test suite and records the result."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import Dict, List, Sequence

from ..configuration import ConfigurationBundle, Diagnostic

logger = logging.getLogger("ember.test")

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class TestAgentSettings:
    enabled: bool
    command: Sequence[str]
    workdir: Path
    report_path: Path
    timeout: float
    env: Dict[str, str]

    @classmethod
    def from_bundle(cls, bundle: ConfigurationBundle) -> "TestAgentSettings":
        raw = bundle.merged.get("test", {}) if bundle.merged else {}
        command = _normalize_command(raw.get("command", "pytest -q"))
        workdir = _resolve_path(REPO_ROOT, raw.get("workdir", "."))
        report_path = _resolve_path(bundle.vault_dir, raw.get("report_path", "state/test-agent.json"))
        timeout = raw.get("timeout", 600)
        try:
            timeout_value = float(timeout)
            if timeout_value <= 0:
                timeout_value = 600
        except (TypeError, ValueError):
            timeout_value = 600
        env_raw = raw.get("env", {}) if isinstance(raw.get("env", {}), dict) else {}
        env: Dict[str, str] = {str(k): str(v) for k, v in env_raw.items()}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            command=command,
            workdir=workdir,
            report_path=report_path,
            timeout=timeout_value,
            env=env,
        )


def run_test_agent(bundle: ConfigurationBundle) -> Dict[str, object]:
    settings = TestAgentSettings.from_bundle(bundle)

    if not settings.enabled:
        detail = "test.agent disabled via configuration."
        logger.info(detail)
        return {"status": "skipped", "detail": detail}

    if bundle.status != "ready":
        detail = f"configuration status '{bundle.status}' is not ready."
        logger.info("test.agent skipped: %s", detail)
        return {"status": "skipped", "detail": detail}

    env = os.environ.copy()
    env.update(settings.env)

    start = time.perf_counter()
    try:
        completed = subprocess.run(
            list(settings.command),
            cwd=settings.workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=settings.timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        message = f"Command '{settings.command[0]}' not found: {exc}"
        logger.error(message)
        bundle.diagnostics.append(
            Diagnostic(level="error", message=message, source=settings.workdir)
        )
        return {
            "status": "error",
            "detail": message,
            "command": " ".join(settings.command),
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start
        message = f"Test command timed out after {settings.timeout}s"
        logger.error(message)
        _write_report(settings.report_path, {
            "status": "timeout",
            "command": exc.cmd,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "duration": duration,
        })
        bundle.diagnostics.append(
            Diagnostic(level="error", message=message, source=settings.report_path)
        )
        return {
            "status": "error",
            "detail": message,
            "command": " ".join(settings.command),
            "report": str(settings.report_path),
        }

    duration = time.perf_counter() - start
    status = "passed" if completed.returncode == 0 else "failed"
    detail = f"exit_code={completed.returncode} duration={duration:.2f}s"

    _write_report(
        settings.report_path,
        {
            "status": status,
            "command": " ".join(settings.command),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "duration": duration,
        },
    )

    logger.info("test.agent completed: %s", detail)
    if completed.returncode != 0:
        bundle.diagnostics.append(
            Diagnostic(
                level="error",
                message="test.agent detected failing tests (see report).",
                source=settings.report_path,
            )
        )

    return {
        "status": status,
        "detail": detail,
        "command": " ".join(settings.command),
        "report": str(settings.report_path),
    }


def _normalize_command(raw: object) -> List[str]:
    if isinstance(raw, str):
        return shlex.split(raw)
    if isinstance(raw, Sequence):
        return [str(part) for part in raw if str(part).strip()]
    return ["pytest", "-q"]


def _resolve_path(base: Path, raw: object) -> Path:
    text = str(raw).strip() if raw is not None else ""
    if not text:
        return base
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


def _write_report(path: Path, payload: Dict[str, object]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:  # pragma: no cover - relies on filesystem conditions
        logger.warning("Unable to write test report to %s: %s", path, exc)


__all__ = ["run_test_agent", "TestAgentSettings"]
