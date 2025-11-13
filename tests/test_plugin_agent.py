"""Tests for plugin.agent."""

from __future__ import annotations

from pathlib import Path

from ember.agents import plugin_loader
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


def test_plugin_agent_discovers_repo_and_vault_plugins(tmp_path: Path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_plugin = repo_root / "plugins" / "hello"
    repo_plugin.mkdir(parents=True)
    (repo_plugin / "plugin.yml").write_text(
        """
name: hello
version: 1.0.0
description: Sample repo plugin
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(plugin_loader, "REPO_ROOT", repo_root)

    bundle = _bundle(tmp_path)
    vault_plugin = bundle.vault_dir / "plugins" / "vault-one"
    vault_plugin.mkdir(parents=True)
    (vault_plugin / "plugin.yml").write_text("name: vault-one\n", encoding="utf-8")

    result = plugin_loader.run_plugin_agent(bundle)

    names = sorted(p["name"] for p in result["plugins"])
    assert names == ["hello", "vault-one"]


def test_plugin_agent_handles_invalid_manifest(tmp_path: Path, monkeypatch):
    repo_root = tmp_path / "repo"
    plugin_dir = repo_root / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yml").write_text("not: [valid\n", encoding="utf-8")
    monkeypatch.setattr(plugin_loader, "REPO_ROOT", repo_root)

    bundle = _bundle(tmp_path)
    result = plugin_loader.run_plugin_agent(bundle)

    assert result["plugins"][0]["status"] == "invalid"
    assert bundle.diagnostics


def test_plugin_agent_can_be_disabled(tmp_path: Path):
    bundle = _bundle(
        tmp_path,
        merged={"plugin": {"enabled": False}},
    )
    result = plugin_loader.run_plugin_agent(bundle)
    assert result["status"] == "skipped"
