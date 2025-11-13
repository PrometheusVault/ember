"""Slash command for runtime status."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..slash_commands import SlashCommand, SlashCommandContext, render_rich

SECTION_ALIASES: Dict[str, Sequence[str]] = {
    "info": ("info", "summary"),
    "diagnostics": ("diagnostics", "diag", "diags"),
    "agents": ("agents", "agent"),
}
DEFAULT_MAX_ROWS = 5


def _resolve_sections(args: Iterable[str]) -> Tuple[List[str], bool]:
    """Return sections to render and whether all rows should be shown."""

    normalized = [arg.strip().lower() for arg in args]
    show_all = any(arg in {"--all", "-a", "all"} for arg in normalized)

    requested: List[str] = []
    for section, aliases in SECTION_ALIASES.items():
        if any(arg in aliases for arg in normalized):
            requested.append(section)

    if not requested:
        requested = list(SECTION_ALIASES.keys())

    return requested, show_all


def _add_rows_with_limit(
    table: Table,
    rows: Sequence[Sequence[str]],
    *,
    max_rows: int,
) -> Tuple[int, bool]:
    """Append up to max_rows rows and return total + truncated flag."""

    for row in rows[:max_rows]:
        table.add_row(*row)

    return len(rows), len(rows) > max_rows


def _handler(context: SlashCommandContext, _: List[str]) -> str:
    config = context.config
    mode = context.metadata.get("mode", "(unknown)")
    sections, show_all = _resolve_sections(_)

    def _render_summary(console: Console) -> None:
        info = Table.grid(padding=(0, 1))
        info.add_column("Key", style="bold", no_wrap=True)
        info.add_column("Value", overflow="fold")
        info.add_row("Vault", str(config.vault_dir))
        info.add_row("Status", config.status)
        info.add_row("Config files", str(len(config.files_loaded)))
        info.add_row("Log path", str(config.log_path or "(not initialized)"))
        info.add_row("Mode", mode)

        console.print(
            Panel(
                info,
                title="Runtime Status",
                border_style="green",
                padding=(0, 1),
            )
        )

    def _render_diagnostics(console: Console) -> None:
        if not config.diagnostics:
            console.print(Panel("[green]No diagnostics reported.", title="Diagnostics", border_style="red"))
            return

        diag_table = Table(
            show_header=True,
            header_style="bold red",
            box=box.SIMPLE,
            pad_edge=False,
        )
        diag_table.add_column("Lvl", style="red", no_wrap=True)
        diag_table.add_column("Message", overflow="fold", ratio=2)
        diag_table.add_column("Source", overflow="fold", ratio=2)

        max_rows = len(config.diagnostics) if show_all else DEFAULT_MAX_ROWS
        rows = [
            (
                diag.level.upper(),
                diag.message,
                str(diag.source or config.vault_dir),
            )
            for diag in config.diagnostics
        ]
        total_rows, truncated = _add_rows_with_limit(diag_table, rows, max_rows=max_rows)

        footer = ""
        if truncated:
            footer = (
                f"\n[dim]Showing {max_rows}/{total_rows}. "
                "Use '/status diagnostics --all' for the full list.[/dim]"
            )
        console.print(
            Panel(
                diag_table if rows else "[green]No diagnostics reported.",
                title="Diagnostics",
                border_style="red",
                padding=(0, 1),
            )
        )
        if footer:
            console.print(footer)

    def _render_agents(console: Console) -> None:
        if not config.agent_state:
            console.print(Panel("[green]No agent records yet.", title="Agents", border_style="blue"))
            return

        agent_table = Table(
            show_header=True,
            header_style="bold blue",
            box=box.SIMPLE,
            pad_edge=False,
        )
        agent_table.add_column("Agent", style="cyan", overflow="fold", ratio=1)
        agent_table.add_column("Status", style="green", no_wrap=True)
        agent_table.add_column("Detail", overflow="fold", ratio=2)

        sorted_agents = sorted(config.agent_state.keys())
        max_rows = len(sorted_agents) if show_all else DEFAULT_MAX_ROWS
        rows = []
        for agent_name in sorted_agents:
            state = config.agent_state.get(agent_name) or {}
            detail = str(state.get("detail") or "").strip()
            last_run = state.get("last_run")
            if last_run:
                timestamp_text = f"last run: {last_run}"
                detail = f"{detail}\n{timestamp_text}" if detail else timestamp_text
            rows.append(
                (
                    agent_name,
                    str(state.get("status", "unknown")).upper(),
                    detail or "(no detail)",
                )
            )
        total_rows, truncated = _add_rows_with_limit(agent_table, rows, max_rows=max_rows)

        footer = ""
        if truncated:
            footer = (
                f"\n[dim]Showing {max_rows}/{total_rows}. "
                "Use '/status agents --all' for the full list.[/dim]"
            )

        console.print(
            Panel(
                agent_table,
                title="Agents",
                border_style="blue",
                padding=(0, 1),
            )
        )
        if footer:
            console.print(footer)

    renderers = {
        "info": _render_summary,
        "diagnostics": _render_diagnostics,
        "agents": _render_agents,
    }

    def _render(console: Console) -> None:
        for section in sections:
            renderers[section](console)

    return render_rich(_render)


COMMAND = SlashCommand(
    name="status",
    description="Show vault, logging, and configuration diagnostics.",
    handler=_handler,
)
