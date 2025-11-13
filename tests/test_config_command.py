from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from ember.commands.config import COMMAND
from ember.configuration import load_runtime_configuration
from ember.slash_commands import CommandRouter, SlashCommandContext


def _build_context(tmp_path: Path) -> tuple[SlashCommandContext, Path]:
    vault_dir = tmp_path / "vault"
    (vault_dir / "config").mkdir(parents=True)
    bundle = load_runtime_configuration(vault_dir)
    router = CommandRouter(bundle, metadata={"repo_root": str(Path(__file__).resolve().parents[1])})
    context = SlashCommandContext(config=bundle, router=router)
    return context, vault_dir


def test_config_set_updates_override_file_and_reload(tmp_path: Path):
    context, vault_dir = _build_context(tmp_path)

    output = COMMAND.handler(context, ["logging.level", "DEBUG"])

    override = vault_dir / "config" / "99-cli-overrides.yml"
    assert override.exists()
    data = yaml.safe_load(override.read_text(encoding="utf-8"))
    assert data["logging"]["level"] == "DEBUG"
    assert context.router.config.merged["logging"]["level"] == "DEBUG"
    assert "logging.level" in output


def test_config_get_returns_value(tmp_path: Path):
    context, vault_dir = _build_context(tmp_path)
    COMMAND.handler(context, ["logging.level", "DEBUG"])

    output = COMMAND.handler(context, ["logging.level"])

    assert 'logging.level = "DEBUG"' in output


def test_config_set_rejects_lists(tmp_path: Path):
    context, _ = _build_context(tmp_path)

    output = COMMAND.handler(context, ["logging.level", "[DEBUG, TRACE]"])

    assert "list values is not supported" in output


def test_config_validate_reports_diagnostics(tmp_path: Path):
    context, _ = _build_context(tmp_path)
    broken = context.config.vault_dir / "config" / "broken.yml"
    broken.write_text("runtime: [\n", encoding="utf-8")

    output = COMMAND.handler(context, ["validate"])

    assert "Diagnostics" in output
    assert "broken.yml" in output
