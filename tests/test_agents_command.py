from pathlib import Path

from ember.commands import COMMANDS
from ember.commands.agents import COMMAND as AGENTS_COMMAND
from ember.configuration import ConfigurationBundle
from ember.slash_commands import CommandRouter, SlashCommandContext


def test_agents_command_lists_registry(tmp_path: Path):
    bundle = ConfigurationBundle(vault_dir=tmp_path, status="ready")
    bundle.agent_state["provision.agent"] = {
        "status": "completed",
        "detail": "verified paths",
    }

    router = CommandRouter(bundle)
    output = AGENTS_COMMAND.handler(
        SlashCommandContext(config=bundle, router=router),
        [],
    )

    assert "provision.agent" in output
    assert "completed" in output
