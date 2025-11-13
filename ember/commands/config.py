"""Slash command for viewing merged configuration."""

from __future__ import annotations

from typing import Any, List

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from ..slash_commands import SlashCommand, SlashCommandContext, render_rich

YAML_FLAGS = {"--yaml", "-y", "yaml"}


def _build_config_tree(data: Any) -> Tree:
    root = Tree("config", guide_style="cyan")
    _add_tree_nodes(root, data)
    return root


def _add_tree_nodes(node: Tree, value: Any, *, label: str | None = None) -> None:
    def _format_scalar(val: Any) -> str:
        if isinstance(val, str):
            truncated = val if len(val) <= 60 else f"{val[:57]}…"
            return f'"{truncated}"'
        return repr(val)

    if isinstance(value, dict):
        branch = node.add(f"[bold]{label}[/]") if label else node
        if not value:
            branch.add("[dim]{ }[/]")
            return
        for key in sorted(value.keys()):
            _add_tree_nodes(branch, value[key], label=str(key))
        return

    if isinstance(value, list):
        title = f"[bold]{label}[/] [dim]list ({len(value)})[/]" if label else f"[dim]list ({len(value)})[/]"
        branch = node.add(title)
        if not value:
            branch.add("[dim][empty][/]")
            return
        for idx, item in enumerate(value):
            _add_tree_nodes(branch, item, label=f"[{idx}]")
        return

    text = _format_scalar(value)
    if label:
        node.add(f"[bold]{label}[/]: {text}")
    else:
        node.add(text)


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    config = context.config
    show_yaml = any(arg.lower() in YAML_FLAGS for arg in args)

    files_table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.SIMPLE,
        pad_edge=False,
    )
    files_table.add_column("Order", justify="right", style="magenta", no_wrap=True)
    files_table.add_column("File", overflow="fold", ratio=1)
    if config.files_loaded:
        for idx, path in enumerate(config.files_loaded, start=1):
            files_table.add_row(str(idx), str(path))
    else:
        files_table.add_row("-", "[dim]No config files loaded[/dim]")

    tree = _build_config_tree(config.merged or {})

    def _render(console: Console) -> None:
        console.print(
            Panel(
                files_table,
                title="Loaded Config Files",
                border_style="magenta",
                padding=(0, 1),
            )
        )
        console.print(
            Panel(
                tree,
                title="Merged Configuration (Tree)",
                border_style="cyan",
                padding=(0, 1),
            )
        )
        if show_yaml:
            yaml_text = yaml.safe_dump(
                config.merged or {},
                sort_keys=True,
                default_flow_style=False,
            ).strip()
            if not yaml_text:
                yaml_text = "# empty configuration"
            syntax = Syntax(yaml_text, "yaml", word_wrap=True)
            console.print(
                Panel(
                    syntax,
                    title="Merged Configuration (YAML)",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
        else:
            console.print(
                "[dim]Tip: use '/config --yaml' to view/export the merged YAML.[/dim]"
            )

    return render_rich(_render)


COMMAND = SlashCommand(
    name="config",
    description="Show merged configuration values and their source files.",
    handler=_handler,
)
