"""Shared slash command registry and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from io import StringIO
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .configuration import ConfigurationBundle

SlashCommandHandler = Callable[["SlashCommandContext", List[str]], str]


class CommandSource(str, Enum):
    USER = "user"
    PLANNER = "planner"


@dataclass
class SlashCommandContext:
    """Context passed into each slash command handler."""

    config: ConfigurationBundle
    router: "CommandRouter"
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: CommandSource = CommandSource.USER


@dataclass
class SlashCommand:
    """Metadata about a slash command."""

    name: str
    description: str
    handler: SlashCommandHandler
    allow_in_planner: bool = True
    requires_ready: bool = False


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

    def handle(
        self,
        command_name: str,
        args: List[str],
        *,
        source: CommandSource = CommandSource.USER,
    ) -> str:
        command = self._commands.get(command_name.lower())
        if command is None:
            return (
                f"[todo] '{command_name}' is not wired yet. "
                "Documented handlers will populate here as agents land."
            )
        if source is CommandSource.PLANNER and not command.allow_in_planner:
            return f"[router] '/{command_name}' is not available to the planner."
        if command.requires_ready and self.config.status != "ready":
            return (
                f"[router] '/{command_name}' requires a ready configuration "
                f"(current status: {self.config.status})."
            )
        context = SlashCommandContext(
            config=self.config,
            router=self,
            metadata=self.metadata,
            source=source,
        )
        return command.handler(context, args)

    @property
    def command_names(self) -> Sequence[str]:
        return sorted(self._commands.keys())

    def commands(self) -> Sequence[SlashCommand]:
        return [self._commands[name] for name in self.command_names]

    def get(self, command_name: str) -> Optional[SlashCommand]:
        return self._commands.get(command_name.lower())

    @property
    def planner_command_names(self) -> Sequence[str]:
        return sorted(
            cmd.name
            for cmd in self._commands.values()
            if cmd.allow_in_planner
        )

    def manpage_path(self, command_name: str) -> Path:
        docs_dir = Path(self.metadata.get("repo_root", Path.cwd())) / "docs" / "commands"
        return docs_dir / f"{command_name.lower()}.md"

    def manpage_exists(self, command_name: str) -> bool:
        return self.manpage_path(command_name).exists()

    def render_manpage(self, command_name: str, paginate: bool = False) -> str:
        path = self.manpage_path(command_name)
        if not path.exists():
            return (
                f"[man] no manual entry for '{command_name}'. "
                f"Create docs/commands/{command_name}.md to document this command."
            )

        content = path.read_text(encoding="utf-8")

        if paginate:
            console = Console(color_system="auto", highlight=True)
            with console.pager(styles=False):
                console.print(Markdown(content), highlight=True, soft_wrap=True)
            return f"[man] displayed manual for '/{command_name}'."

        def _render(console: Console) -> None:
            console.print(Markdown(content))

        return render_rich(_render)


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
    "CommandSource",
    "render_help_table",
    "render_rich",
]
