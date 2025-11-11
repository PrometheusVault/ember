"""Slash command for listing available commands."""

from __future__ import annotations

from typing import List

from ..slash_commands import (
    SlashCommand,
    SlashCommandContext,
    render_help_table,
)


def _handler(context: SlashCommandContext, _: List[str]) -> str:
    return render_help_table(context.router.commands())


COMMAND = SlashCommand(
    name="help",
    description="List available slash commands.",
    handler=_handler,
)
