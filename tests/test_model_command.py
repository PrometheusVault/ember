from pathlib import Path

from ember.ai import LlamaSession
from ember.commands.model import COMMAND as MODEL_COMMAND
from ember.slash_commands import CommandRouter, SlashCommandContext
from ember.configuration import ConfigurationBundle


def test_model_lists_current(tmp_path: Path):
    bundle = ConfigurationBundle(vault_dir=tmp_path, status="ready")
    router = CommandRouter(bundle)
    session = LlamaSession(model_path=tmp_path / "models" / "a.gguf")
    router.metadata["llama_session"] = session

    result = MODEL_COMMAND.handler(
        SlashCommandContext(config=bundle, router=router, metadata=router.metadata),
        [],
    )

    assert "Current model" in result


def test_model_set_updates_path(tmp_path: Path):
    bundle = ConfigurationBundle(vault_dir=tmp_path, status="ready")
    router = CommandRouter(bundle)
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    target = models_dir / "demo.gguf"
    target.write_text("fake")

    session = LlamaSession(model_path=target)
    router.metadata["llama_session"] = session

    result = MODEL_COMMAND.handler(
        SlashCommandContext(config=bundle, router=router, metadata=router.metadata),
        ["set", str(target)],
    )

    assert "switched" in result
    assert session.model_path == target
