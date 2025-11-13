"""Slash command for viewing and editing configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from ..configuration import ConfigurationBundle, load_runtime_configuration
from ..slash_commands import SlashCommand, SlashCommandContext, render_rich

YAML_FLAGS = {"--yaml", "-y", "yaml"}
CLI_OVERRIDE_FILENAME = "99-cli-overrides.yml"


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
    if not args:
        return _render_config_view(context.config, show_yaml=False)

    if all(arg.lower() in YAML_FLAGS for arg in args):
        return _render_config_view(context.config, show_yaml=True)

    key_expr = args[0]
    try:
        key_parts = _parse_key_path(key_expr)
    except ConfigMutationError as exc:
        return str(exc)

    if len(args) == 1:
        return _handle_get_value(context.config, key_parts)

    value_raw = " ".join(args[1:]).strip()
    if not value_raw:
        return "[config] value cannot be empty."

    return _handle_set_value(context, key_parts, value_raw)


def _render_config_view(bundle: ConfigurationBundle, show_yaml: bool) -> str:
    files_table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.SIMPLE,
        pad_edge=False,
    )
    files_table.add_column("Order", justify="right", style="magenta", no_wrap=True)
    files_table.add_column("File", overflow="fold", ratio=1)
    if bundle.files_loaded:
        for idx, path in enumerate(bundle.files_loaded, start=1):
            files_table.add_row(str(idx), str(path))
    else:
        files_table.add_row("-", "[dim]No config files loaded[/dim]")

    tree = _build_config_tree(bundle.merged or {})

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
                bundle.merged or {},
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


def _handle_get_value(config: ConfigurationBundle, key_parts: List[str]) -> str:
    value = _lookup_path(config.merged, key_parts)
    dotted = ".".join(key_parts)
    if value is None:
        return f"[config] {dotted} is not set."
    return f"[config] {dotted} = {_format_value(value)}"


def _handle_set_value(
    context: SlashCommandContext,
    key_parts: List[str],
    value_raw: str,
) -> str:
    try:
        value = yaml.safe_load(value_raw)
    except yaml.YAMLError as exc:
        return f"[config] could not parse value: {exc}"

    if isinstance(value, list):
        return "[config] setting list values is not supported yet."
    override_path = _override_file_path(context.config.vault_dir)

    if isinstance(value, dict):
        return "[config] setting nested mappings is not supported yet."

    override_path = _override_file_path(context.config.vault_dir)

    try:
        data = _load_override_data(override_path)
        _assign_key(data, key_parts, value)
        _write_override_data(override_path, data)
    except ConfigMutationError as exc:
        return str(exc)

    bundle = _reload_configuration(context)
    new_value = _lookup_path(bundle.merged, key_parts)
    location = _friendly_path(override_path, bundle.vault_dir)
    dotted = ".".join(key_parts)
    return (
        f"[config] {dotted} updated to {_format_value(new_value)} "
        f"(stored in {location})"
    )


COMMAND = SlashCommand(
    name="config",
    description="Show merged configuration values and their source files.",
    handler=_handler,
)


class ConfigMutationError(RuntimeError):
    """Signals a failure while editing vault overrides."""


def _override_file_path(vault_dir: Path) -> Path:
    return vault_dir / "config" / CLI_OVERRIDE_FILENAME


def _parse_key_path(expr: str) -> List[str]:
    parts = [segment.strip() for segment in expr.split(".") if segment.strip()]
    if not parts:
        raise ConfigMutationError("[config] key path cannot be empty.")
    return parts


def _load_override_data(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigMutationError(f"[config] failed to read {path}: {exc}") from exc
    if not raw.strip():
        return {}
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ConfigMutationError(f"[config] could not parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigMutationError(
            f"[config] override file '{path}' must contain a mapping."
        )
    return data


def _write_override_data(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigMutationError(
            f"[config] failed to create directory '{path.parent}': {exc}"
        ) from exc
    if data:
        serialized = yaml.safe_dump(
            data,
            sort_keys=True,
            default_flow_style=False,
        )
        try:
            path.write_text(serialized, encoding="utf-8")
        except OSError as exc:
            raise ConfigMutationError(f"[config] failed to write {path}: {exc}") from exc
    else:
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                raise ConfigMutationError(f"[config] failed to remove {path}: {exc}") from exc


def _assign_key(data: Dict[str, Any], parts: List[str], value: Any) -> None:
    cursor: Dict[str, Any] = data
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def _lookup_path(data: Any, parts: List[str]) -> Any:
    cursor = data
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def _reload_configuration(context: SlashCommandContext):
    bundle = load_runtime_configuration(context.config.vault_dir)
    context.router.config = bundle
    context.config = bundle
    return bundle


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    return repr(value)


def _friendly_path(path: Path, vault_dir: Path) -> str:
    try:
        return str(path.relative_to(vault_dir))
    except ValueError:
        return str(path)
