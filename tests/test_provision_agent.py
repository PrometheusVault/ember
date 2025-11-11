"""Tests for the provision agent."""

from __future__ import annotations

import json
from pathlib import Path

from ember.agents import provision
from ember.configuration import ConfigurationBundle


def _bundle(vault_dir: Path, merged: dict | None = None) -> ConfigurationBundle:
    return ConfigurationBundle(
        vault_dir=vault_dir,
        status="ready",
        merged=merged or {},
    )


def test_provision_agent_creates_required_paths(tmp_path: Path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    bundle = _bundle(
        vault_dir,
        merged={"provision": {"required_paths": ["logs", "plugins/custom"]}},
    )

    result = provision.run_provision_agent(bundle)

    assert result.status == "completed"
    assert (vault_dir / "logs").is_dir()
    assert (vault_dir / "plugins/custom").is_dir()
    assert result.state_path == vault_dir / "state/provision.json"

    payload = json.loads(result.state_path.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    logs_path = str(vault_dir / "logs")
    assert logs_path in payload["created"] or logs_path in payload["verified"]


def test_provision_agent_skips_when_env_set(tmp_path: Path, monkeypatch):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    bundle = _bundle(vault_dir)
    monkeypatch.setenv("EMBER_SKIP_PROVISION", "1")

    result = provision.run_provision_agent(bundle)

    assert result.status == "skipped"
    assert not (vault_dir / "logs").exists()


def test_provision_agent_records_diagnostics_for_files(tmp_path: Path):
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "logs").write_text("not a dir", encoding="utf-8")
    bundle = _bundle(vault_dir, merged={"provision": {"required_paths": ["logs"]}})

    result = provision.run_provision_agent(bundle)

    assert result.status == "partial"
    assert bundle.diagnostics
    assert bundle.diagnostics[-1].level == "error"
