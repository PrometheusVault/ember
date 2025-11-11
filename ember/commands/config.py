"""Slash command for viewing merged configuration."""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..slash_commands import SlashCommand, SlashCommandContext, render_rich


def _flatten_rows(table: Table, prefix: str, value) -> None:
    if isinstance(value, dict):
        for sub_key in sorted(value.keys()):
            next_prefix = f"{prefix}.{sub_key}" if prefix else sub_key
            _flatten_rows(table, next_prefix, value[sub_key])
    else:
        table.add_row(prefix or "(root)", repr(value))


def _handler(context: SlashCommandContext, _: List[str]) -> str:
    config = context.config

    files_table = Table(show_header=True, header_style="bold magenta")
    files_table.add_column("Order", justify="right", style="magenta")
    files_table.add_column("File", overflow="fold")
    for idx, path in enumerate(config.files_loaded, start=1):
        files_table.add_row(str(idx), str(path))

    merged_table = Table(show_header=True, header_style="bold cyan")
    merged_table.add_column("Key", style="green")
    merged_table.add_column("Value", overflow="fold")
    _flatten_rows(merged_table, "", config.merged)

    def _render(console: Console) -> None:
        console.print(Panel(files_table, title="Loaded Config Files", border_style="magenta"))
        console.print(Panel(merged_table, title="Merged Configuration", border_style="cyan"))

    return render_rich(_render)


COMMAND = SlashCommand(
    name="config",
    description="Show merged configuration values and their source files.",
    handler=_handler,
)
