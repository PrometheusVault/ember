"""Slash command for displaying command execution history."""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.table import Table

from ..slash_commands import (
    SlashCommand,
    SlashCommandContext,
    render_rich,
)


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    """Display command execution history with optional filtering."""

    history = context.metadata.get("history", [])

    # Parse arguments
    search_term = None
    limit = 20

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-n", "--limit") and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg in ("-s", "--search") and i + 1 < len(args):
            search_term = args[i + 1]
            i += 2
        elif not arg.startswith("-"):
            search_term = arg
            i += 1
        else:
            i += 1

    if not history:
        return "[history] No commands executed yet in this session."

    # Filter by search term
    filtered = history
    if search_term:
        search_lower = search_term.lower()
        filtered = [h for h in history if search_lower in h.command.lower()]

    if not filtered:
        return f"[history] No commands matching '{search_term}' found."

    # Limit results (show most recent)
    filtered = filtered[-limit:]

    def _render(console: Console) -> None:
        table = Table(
            title=f"Command History (showing {len(filtered)} of {len(history)})",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Command", style="green", no_wrap=True)
        table.add_column("Output Preview", style="dim", max_width=50, overflow="ellipsis")

        for i, entry in enumerate(filtered, 1):
            # Truncate output preview
            output = entry.output or ""
            preview = output[:80].replace("\n", " ").strip()
            if len(output) > 80:
                preview += "..."

            table.add_row(str(i), f"/{entry.command}", preview)

        console.print(table)

    return render_rich(_render)


COMMAND = SlashCommand(
    name="history",
    description="Show command execution history. Usage: /history [-n LIMIT] [-s SEARCH]",
    handler=_handler,
    allow_in_planner=False,
)
