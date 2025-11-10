"""Tests for the vault-aware configuration loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from ember import configuration


def _prepare_repo_defaults(tmp_path: Path, content: str = "foo: bar\n") -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "10-default.yml").write_text(content, encoding="utf-8")
    return config_dir


def test_resolve_vault_dir_uses_env_expansion(tmp_path: Path):
    env = {"VAULT_DIR": str(tmp_path / "vault")}
    path = configuration.resolve_vault_dir(env=env)
    assert path == tmp_path / "vault"


def test_load_runtime_configuration_merges_repo_and_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_dir = _prepare_repo_defaults(tmp_path, content="runtime:\n  mode: dev\n")
    vault_dir = tmp_path / "vault"
    overrides_dir = vault_dir / "config"
    overrides_dir.mkdir(parents=True)
    (overrides_dir / "20-overrides.yml").write_text(
        "runtime:\n  mode: prod\n  debug: false\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(configuration, "DEFAULT_CONFIG_DIR", repo_dir)

    bundle = configuration.load_runtime_configuration(vault_dir)

    assert bundle.status == "ready"
    assert bundle.merged["runtime"]["mode"] == "prod"
    assert bundle.merged["runtime"]["debug"] is False
    assert len(bundle.files_loaded) == 2


def test_load_runtime_configuration_reports_missing_vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_dir = _prepare_repo_defaults(tmp_path)
    missing_vault = tmp_path / "missing"
    monkeypatch.setattr(configuration, "DEFAULT_CONFIG_DIR", repo_dir)

    bundle = configuration.load_runtime_configuration(missing_vault)

    assert bundle.status == "missing"
    assert any(diag.level == "error" for diag in bundle.diagnostics)


def test_load_runtime_configuration_handles_bad_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_dir = _prepare_repo_defaults(tmp_path)
    vault_dir = tmp_path / "vault"
    overrides_dir = vault_dir / "config"
    overrides_dir.mkdir(parents=True)
    (overrides_dir / "broken.yml").write_text("runtime: [\n", encoding="utf-8")

    monkeypatch.setattr(configuration, "DEFAULT_CONFIG_DIR", repo_dir)

    bundle = configuration.load_runtime_configuration(vault_dir)

    assert bundle.status == "invalid"
    assert any("Failed to parse" in diag.message for diag in bundle.diagnostics)
