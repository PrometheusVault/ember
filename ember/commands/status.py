"""Slash command for runtime status."""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..slash_commands import SlashCommand, SlashCommandContext, render_rich


def _handler(context: SlashCommandContext, _: List[str]) -> str:
    config = context.config
    mode = context.metadata.get("mode", "(unknown)")

    info = Table.grid(padding=(0, 2))
    info.add_row("Vault", str(config.vault_dir))
    info.add_row("Status", config.status)
    info.add_row("Config files", str(len(config.files_loaded)))
    info.add_row("Log path", str(config.log_path or "(not initialized)"))
    info.add_row("Mode", mode)

    def _render(console: Console) -> None:
        console.print(Panel(info, title="Runtime Status", border_style="green"))
        if config.diagnostics:
            diag_table = Table(show_header=True, header_style="bold red")
            diag_table.add_column("Level", style="red")
            diag_table.add_column("Message")
            diag_table.add_column("Source", overflow="fold")
            for diag in config.diagnostics:
                source = str(diag.source or config.vault_dir)
                diag_table.add_row(diag.level.upper(), diag.message, source)
            console.print(Panel(diag_table, title="Diagnostics", border_style="red"))
        if config.agent_state:
            agent_table = Table(show_header=True, header_style="bold blue")
            agent_table.add_column("Agent", style="cyan", no_wrap=True)
            agent_table.add_column("Status", style="green")
            agent_table.add_column("Detail", overflow="fold")
            for agent_name in sorted(config.agent_state.keys()):
                state = config.agent_state.get(agent_name) or {}
                detail = str(state.get("detail") or "").strip()
                last_run = state.get("last_run")
                if last_run:
                    timestamp_text = f"last run: {last_run}"
                    detail = f"{detail} ({timestamp_text})" if detail else timestamp_text
                agent_table.add_row(
                    agent_name,
                    str(state.get("status", "unknown")).upper(),
                    detail or "(no detail)",
                )
            console.print(Panel(agent_table, title="Agents", border_style="blue"))

    return render_rich(_render)


COMMAND = SlashCommand(
    name="status",
    description="Show vault, logging, and configuration diagnostics.",
    handler=_handler,
)
