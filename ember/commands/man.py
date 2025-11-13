"""Slash command for displaying command manpages."""

from __future__ import annotations

from typing import List

from ..slash_commands import SlashCommand, SlashCommandContext


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    if not args:
        commands_with_docs = [cmd for cmd in context.router.commands() if context.router.manpage_exists(cmd.name)]
        if not commands_with_docs:
            return "[man] no manpages found. Place files under docs/commands/."
        names = ", ".join(f"/{cmd.name}" for cmd in commands_with_docs)
        return (
            "[man] provide a command name. Available manpages: "
            f"{names}"
        )

    command_name = args[0]
    if context.router.get(command_name) is None:
        return f"[man] unknown command '{command_name}'. Use /help for a list of commands."

    return context.router.render_manpage(command_name, paginate=True)


COMMAND = SlashCommand(
    name="man",
    description="Show the detailed manual for a slash command.",
    handler=_handler,
    allow_in_planner=False,
)
