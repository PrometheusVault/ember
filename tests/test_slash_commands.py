"""Unit tests for slash command registry."""

from __future__ import annotations

from pathlib import Path

from ember.configuration import ConfigurationBundle
from ember.slash_commands import (
    CommandRouter,
    SlashCommand,
    SlashCommandContext,
    render_help_table,
    render_rich,
)


def test_router_handles_registered_command(tmp_path: Path):
    config = ConfigurationBundle(vault_dir=tmp_path, status="ready")
    router = CommandRouter(config)
    captured = {}

    def handler(context: SlashCommandContext, args: list[str]) -> str:
        captured["context"] = context
        return f"echo:{' '.join(args)}"

    router.register(SlashCommand(name="echo", description="Echo args", handler=handler))
    result = router.handle("echo", ["hello", "world"])

    assert result == "echo:hello world"
    assert captured["context"].config is config
    assert "echo" in router.command_names


def test_render_help_table_lists_commands(tmp_path: Path):
    config = ConfigurationBundle(vault_dir=tmp_path, status="ready")
    router = CommandRouter(config)
    router.register(SlashCommand(name="status", description="Show status", handler=lambda *_: ""))
    router.register(SlashCommand(name="help", description="Show help", handler=lambda *_: ""))

    output = render_help_table(router.commands())

    assert "/status" in output
    assert "Show status" in output


def test_render_rich_produces_ansi(tmp_path: Path):
    config = ConfigurationBundle(vault_dir=tmp_path, status="ready")

    def _render(console):
        console.print("hello", style="bold red")

    ansi = render_rich(_render)

    assert "\x1b[" in ansi  # contains ANSI escape sequence
