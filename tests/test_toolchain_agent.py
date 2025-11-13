"""Tests for the toolchain agent."""

from __future__ import annotations

from pathlib import Path

from ember.agents import toolchain
from ember.configuration import ConfigurationBundle


def _bundle(tmp_path: Path, *, manifest: Path | None = None) -> ConfigurationBundle:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    merged: dict = {}
    if manifest is not None:
        merged["toolchain"] = {"manifest": str(manifest)}
    return ConfigurationBundle(
        vault_dir=vault_dir,
        status="ready",
        merged=merged,
        diagnostics=[],
    )


def test_toolchain_agent_reports_missing_requirements(tmp_path: Path):
    manifest = tmp_path / "toolchain.yml"
    manifest.write_text(
        """
commands:
  - name: echo
  - name: definitely_missing
python:
  - module: sys
  - module: not_a_module
files:
  - path: missing.file
env:
  - name: TOTALLY_OPTIONAL
    optional: true
""",
        encoding="utf-8",
    )

    bundle = _bundle(tmp_path, manifest=manifest)
    result = toolchain.run_toolchain_agent(bundle)

    assert result["status"] == "degraded"
    commands = {item["name"]: item for item in result["commands"]}
    assert commands["echo"]["available"] is True
    assert commands["definitely_missing"]["available"] is False
    python = {item["module"]: item for item in result["python"]}
    assert python["sys"]["available"] is True
    assert python["not_a_module"]["available"] is False
    files = result["files"]
    assert files[0]["available"] is False


def test_toolchain_agent_marks_optional_items(tmp_path: Path, monkeypatch):
    manifest = tmp_path / "toolchain.yml"
    manifest.write_text(
        """
commands:
  - name: absolutely_missing
    optional: true
python:
  - module: made_up_lib
    optional: true
""",
        encoding="utf-8",
    )

    bundle = _bundle(tmp_path, manifest=manifest)
    result = toolchain.run_toolchain_agent(bundle)

    assert result["status"] == "ok"
    assert result["commands"][0]["optional"] is True


def test_toolchain_agent_missing_manifest(tmp_path: Path):
    manifest = tmp_path / "not-there.yml"
    bundle = _bundle(tmp_path, manifest=manifest)

    result = toolchain.run_toolchain_agent(bundle)

    assert result["status"] == "error"
    assert bundle.diagnostics
