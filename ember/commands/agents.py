"""Slash command for listing agent metadata."""

from __future__ import annotations

from typing import List

from rich.table import Table

from ..agents import REGISTRY
from ..slash_commands import SlashCommand, SlashCommandContext, render_rich


def _handler(context: SlashCommandContext, _: List[str]) -> str:
    bundle = context.config
    enabled_map = REGISTRY.enabled(bundle)
    table = Table(title="Registered Agents", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="green", no_wrap=True)
    table.add_column("Enabled", style="magenta", no_wrap=True)
    table.add_column("Status", style="yellow")
    table.add_column("Detail", overflow="fold")

    agent_state = bundle.agent_state or {}

    for definition in sorted(REGISTRY.definitions(), key=lambda d: d.name):
        key = definition.name.lower()
        enabled = enabled_map.get(key, definition.default_enabled)
        state = agent_state.get(definition.name, {})
        status = str(state.get("status", "(never run)"))
        detail = str(state.get("detail", "")).strip() or ""

        table.add_row(
            definition.name,
            "yes" if enabled else "no",
            status,
            detail,
        )

    return render_rich(lambda console: console.print(table))


COMMAND = SlashCommand(
    name="agents",
    description="Show registered agents and their latest results.",
    handler=_handler,
    allow_in_planner=False,
)
