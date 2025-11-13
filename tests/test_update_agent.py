"""Tests for update.agent."""

from __future__ import annotations

from pathlib import Path
import subprocess

from ember.agents import update_agent
from ember.configuration import ConfigurationBundle


def _bundle(tmp_path: Path, merged: dict | None = None) -> ConfigurationBundle:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    return ConfigurationBundle(
        vault_dir=vault_dir,
        status="ready",
        merged=merged or {},
        diagnostics=[],
    )


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE)
    (path / "README.md").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, stdout=subprocess.PIPE)


def test_update_agent_reports_git_status(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    monkeypatch.setattr(update_agent, "REPO_ROOT", repo)

    bundle = _bundle(tmp_path, merged={"update": {"enabled": True}})
    result = update_agent.run_update_agent(bundle)

    assert result["status"] == "ok"
    assert "branch=" in result["detail"]


def test_update_agent_marks_dirty_tree(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "README.md").write_text("dirty", encoding="utf-8")
    monkeypatch.setattr(update_agent, "REPO_ROOT", repo)

    bundle = _bundle(tmp_path, merged={"update": {"enabled": True}})
    result = update_agent.run_update_agent(bundle)

    assert result["status"] == "degraded"


def test_update_agent_handles_missing_git(tmp_path: Path, monkeypatch):
    bundle = _bundle(tmp_path, merged={"update": {"enabled": True}})

    def fake_run_git(*_, **__):  # pragma: no cover - error path
        raise FileNotFoundError("git")

    monkeypatch.setattr(update_agent, "_run_git", fake_run_git)

    result = update_agent.run_update_agent(bundle)

    assert result["status"] == "error"
    assert bundle.diagnostics
