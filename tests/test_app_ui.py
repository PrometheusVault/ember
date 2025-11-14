"""Tests covering UI verbosity resolution helpers."""

from __future__ import annotations

from pathlib import Path

from ember.app import _resolve_ui_verbose
from ember.configuration import ConfigurationBundle


def _bundle(merged: dict | None = None) -> ConfigurationBundle:
    return ConfigurationBundle(
        vault_dir=Path("/tmp/vault"),
        status="ready",
        merged=merged or {},
    )


def test_resolve_ui_verbose_defaults_to_true():
    bundle = _bundle()
    assert _resolve_ui_verbose(bundle) is True


def test_resolve_ui_verbose_reads_config():
    bundle = _bundle({"ui": {"verbose": False}})
    assert _resolve_ui_verbose(bundle) is False


def test_resolve_ui_verbose_env_override(monkeypatch):
    bundle = _bundle({"ui": {"verbose": True}})
    monkeypatch.setenv("EMBER_UI_VERBOSE", "0")
    assert _resolve_ui_verbose(bundle) is False
