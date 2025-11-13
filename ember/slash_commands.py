"""Shared slash command registry and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
import shutil
from typing import Any, Callable, Dict, List, Optional, Sequence

from rich.console import Console
from rich.table import Table

from .configuration import ConfigurationBundle

SlashCommandHandler = Callable[["SlashCommandContext", List[str]], str]


@dataclass
class SlashCommandContext:
    """Context passed into each slash command handler."""

    config: ConfigurationBundle
    router: "CommandRouter"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SlashCommand:
    """Metadata about a slash command."""

    name: str
    description: str
    handler: SlashCommandHandler


class CommandRouter:
    """Registry + dispatcher for slash commands."""

    def __init__(
        self,
        config: ConfigurationBundle,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = config
        self._commands: Dict[str, SlashCommand] = {}
        self.metadata = metadata or {}

    def register(self, command: SlashCommand) -> None:
        self._commands[command.name.lower()] = command

    def handle(self, command_name: str, args: List[str]) -> str:
        command = self._commands.get(command_name.lower())
        if command is None:
            return (
                f"[todo] '{command_name}' is not wired yet. "
                "Documented handlers will populate here as agents land."
            )
        context = SlashCommandContext(
            config=self.config,
            router=self,
            metadata=self.metadata,
        )
        return command.handler(context, args)

    @property
    def command_names(self) -> Sequence[str]:
        return sorted(self._commands.keys())

    def commands(self) -> Sequence[SlashCommand]:
        return [self._commands[name] for name in self.command_names]


def render_help_table(commands: Sequence[SlashCommand]) -> str:
    """Render a help table listing slash commands."""

    def _render(console: Console) -> None:
        table = Table(title="Slash Commands", show_header=True, header_style="bold cyan")
        table.add_column("Command", style="green", no_wrap=True)
        table.add_column("Description")
        for cmd in commands:
            table.add_row(f"/{cmd.name}", cmd.description)
        console.print(table)

    return render_rich(_render)


def render_rich(render_fn: Callable[[Console], None]) -> str:
    """Render a Rich layout to an ANSI string without printing live."""

    terminal_size = shutil.get_terminal_size(fallback=(80, 24))
    # Clamp to a reasonable minimum so Rich does not choke on ultra-small widths.
    width = max(20, terminal_size.columns)
    height = max(10, terminal_size.lines)

    console = Console(
        record=True,
        force_terminal=True,
        color_system="auto",
        width=width,
        height=height,
        file=StringIO(),
    )
    render_fn(console)
    return console.export_text(clear=False, styles=True)


__all__ = [
    "SlashCommand",
    "SlashCommandContext",
    "CommandRouter",
    "render_help_table",
    "render_rich",
]
