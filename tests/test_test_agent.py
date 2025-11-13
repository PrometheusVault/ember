"""Tests for test.agent."""

from __future__ import annotations

from pathlib import Path

from ember.agents import test_runner
from ember.configuration import ConfigurationBundle


def _bundle(tmp_path: Path, merged: dict | None = None, status: str = "ready") -> ConfigurationBundle:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    return ConfigurationBundle(
        vault_dir=vault_dir,
        status=status,  # type: ignore[arg-type]
        merged=merged or {},
        diagnostics=[],
    )


def test_test_agent_runs_command_and_writes_report(tmp_path: Path):
    bundle = _bundle(
        tmp_path,
        merged={
            "test": {
                "enabled": True,
                "command": ["python3", "-c", "print('ok')"],
                "report_path": "state/test-result.json",
            }
        },
    )

    result = test_runner.run_test_agent(bundle)

    assert result["status"] == "passed"
    report_path = bundle.vault_dir / "state" / "test-result.json"
    assert report_path.exists()
    assert "exit_code" in result["detail"]


def test_test_agent_handles_failures(tmp_path: Path):
    bundle = _bundle(
        tmp_path,
        merged={
            "test": {
                "enabled": True,
                "command": ["python3", "-c", "import sys; sys.exit(3)"],
            }
        },
    )

    result = test_runner.run_test_agent(bundle)

    assert result["status"] == "failed"
    assert bundle.diagnostics  # diagnostic recorded for failure


def test_test_agent_skips_when_disabled(tmp_path: Path):
    bundle = _bundle(tmp_path, merged={"test": {"enabled": False}})
    result = test_runner.run_test_agent(bundle)
    assert result["status"] == "skipped"


def test_test_agent_reports_missing_command(tmp_path: Path):
    bundle = _bundle(
        tmp_path,
        merged={
            "test": {
                "enabled": True,
                "command": ["def-not-real-command"],
            }
        },
    )

    result = test_runner.run_test_agent(bundle)

    assert result["status"] == "error"
    assert any("def-not-real-command" in diag.message for diag in bundle.diagnostics)
