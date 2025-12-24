"""Slash command for vault synchronization."""

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
    """Manage vault synchronization."""

    if not args:
        return _show_status(context)

    subcommand = args[0].lower()

    if subcommand == "status":
        return _show_status(context)
    elif subcommand == "pull":
        return _run_sync(context, "pull")
    elif subcommand == "push":
        return _run_sync(context, "push")
    elif subcommand == "sync":
        return _run_sync(context, "full")
    elif subcommand == "manifest":
        return _show_manifest(context)
    elif subcommand == "diff":
        return _show_diff(context)
    elif subcommand == "help":
        return _show_help()
    else:
        return f"[sync] Unknown subcommand '{subcommand}'. Use /sync help for usage."


def _show_status(context: SlashCommandContext) -> str:
    """Show sync status."""
    sync_config = context.config.merged.get("sync", {}) if context.config.merged else {}

    def _render(console: Console) -> None:
        table = Table(title="Vault Sync Status", show_header=False)
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("Enabled", str(sync_config.get("enabled", False)))
        table.add_row("Mode", sync_config.get("mode", "manual"))
        table.add_row("Node ID", sync_config.get("node_id") or "(auto)")
        table.add_row("Server URL", sync_config.get("server_url") or "(not configured)")
        table.add_row("Conflict Strategy", sync_config.get("conflict_strategy", "newest_wins"))

        # Sync directories
        sync_dirs = sync_config.get("sync_dirs", ["config", "library", "notes", "reference"])
        table.add_row("Sync Dirs", ", ".join(sync_dirs))

        # Exclude patterns
        exclude = sync_config.get("exclude_patterns", [])
        table.add_row("Exclude", ", ".join(exclude[:5]) + ("..." if len(exclude) > 5 else ""))

        # Check for manifest
        manifest_path = sync_config.get("manifest_path", "state/sync_manifest.json")
        full_manifest_path = context.config.vault_dir / manifest_path
        table.add_row("Manifest", str(manifest_path))
        table.add_row("Has Manifest", str(full_manifest_path.exists()))

        if full_manifest_path.exists() and sync_config.get("enabled", False):
            try:
                from ..sync import VaultManifest
                manifest = VaultManifest.load(full_manifest_path)
                if manifest:
                    table.add_row("Tracked Files", str(len(manifest.files)))
                    table.add_row("Last Sync", manifest.created_at or "(unknown)")
            except Exception as e:
                table.add_row("Manifest Error", str(e))

        console.print(table)

    return render_rich(_render)


def _run_sync(context: SlashCommandContext, sync_type: str) -> str:
    """Run sync operation."""
    sync_config = context.config.merged.get("sync", {}) if context.config.merged else {}

    if not sync_config.get("enabled", False):
        return "[sync] Sync is disabled. Enable it in configuration first."

    server_url = sync_config.get("server_url")
    if not server_url:
        return "[sync] No server URL configured. Set sync.server_url in configuration."

    try:
        from ..sync import SyncClient, SyncSettings

        settings = SyncSettings.from_config(context.config.merged)
        client = SyncClient(context.config.vault_dir, settings)

        result = client.sync_with_server(server_url)

        if result.success:
            lines = [f"[sync] Sync completed: {result.message}"]
            if result.uploaded > 0:
                lines.append(f"  Uploaded: {result.uploaded} files")
            if result.downloaded > 0:
                lines.append(f"  Downloaded: {result.downloaded} files")
            if result.conflicts_resolved > 0:
                lines.append(f"  Conflicts resolved: {result.conflicts_resolved}")
            if result.conflicts_pending > 0:
                lines.append(f"  Conflicts pending: {result.conflicts_pending}")
            return "\n".join(lines)
        else:
            return f"[sync] Sync failed: {result.message}"

    except Exception as e:
        return f"[sync] Sync error: {e}"


def _show_manifest(context: SlashCommandContext) -> str:
    """Show current manifest contents."""
    sync_config = context.config.merged.get("sync", {}) if context.config.merged else {}

    if not sync_config.get("enabled", False):
        return "[sync] Sync is disabled. Enable it in configuration first."

    try:
        from ..sync import SyncClient, SyncSettings

        settings = SyncSettings.from_config(context.config.merged)
        client = SyncClient(context.config.vault_dir, settings)

        manifest = client.load_manifest()
        if manifest is None:
            # Build a fresh manifest
            manifest = client.build_manifest()

        def _render(console: Console) -> None:
            console.print(f"[bold]Vault Manifest[/bold] ({len(manifest.files)} files)\n")

            table = Table(show_header=True)
            table.add_column("Path", style="cyan")
            table.add_column("Size", justify="right")
            table.add_column("Hash", style="dim", max_width=16)

            # Sort by path
            for path in sorted(manifest.files.keys())[:50]:
                info = manifest.files[path]
                size_str = _format_size(info.size)
                hash_short = info.hash[:12] + "..."
                table.add_row(path, size_str, hash_short)

            if len(manifest.files) > 50:
                console.print(f"(showing first 50 of {len(manifest.files)} files)")

            console.print(table)

        return render_rich(_render)

    except Exception as e:
        return f"[sync] Error showing manifest: {e}"


def _show_diff(context: SlashCommandContext) -> str:
    """Show pending changes since last sync."""
    sync_config = context.config.merged.get("sync", {}) if context.config.merged else {}

    if not sync_config.get("enabled", False):
        return "[sync] Sync is disabled. Enable it in configuration first."

    try:
        from ..sync import SyncClient, SyncSettings

        settings = SyncSettings.from_config(context.config.merged)
        client = SyncClient(context.config.vault_dir, settings)

        delta = client.compute_local_delta()

        if delta is None:
            # No previous manifest - all files are "new"
            manifest = client.build_manifest()
            return f"[sync] No previous sync. {len(manifest.files)} files to track."

        if not delta.has_changes:
            return "[sync] No changes since last sync."

        def _render(console: Console) -> None:
            console.print(f"[bold]Changes since last sync:[/bold]\n")
            console.print(f"Summary: {delta.summary()}\n")

            if delta.to_upload:
                console.print("[green]To Upload:[/green]")
                for change in delta.to_upload[:10]:
                    console.print(f"  + {change.path} ({change.action.value})")
                if len(delta.to_upload) > 10:
                    console.print(f"  ... and {len(delta.to_upload) - 10} more")
                console.print()

            if delta.to_download:
                console.print("[blue]To Download:[/blue]")
                for change in delta.to_download[:10]:
                    console.print(f"  - {change.path} ({change.action.value})")
                if len(delta.to_download) > 10:
                    console.print(f"  ... and {len(delta.to_download) - 10} more")
                console.print()

            if delta.conflicts:
                console.print("[yellow]Conflicts:[/yellow]")
                for change in delta.conflicts[:10]:
                    console.print(f"  ! {change.path}")
                if len(delta.conflicts) > 10:
                    console.print(f"  ... and {len(delta.conflicts) - 10} more")

        return render_rich(_render)

    except Exception as e:
        return f"[sync] Error computing diff: {e}"


def _format_size(size: int) -> str:
    """Format file size in human-readable form."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def _show_help() -> str:
    """Show sync command help."""
    return """[sync] Usage:
  /sync              Show sync status
  /sync status       Show sync status
  /sync pull         Download changes from server
  /sync push         Upload changes to server
  /sync sync         Full bidirectional sync
  /sync manifest     Show current file manifest
  /sync diff         Show pending changes since last sync
  /sync help         Show this help

Configuration (in vault config):
  sync:
    enabled: true
    node_id: my-node
    mode: manual       # manual or auto
    server_url: http://sync-server:8000
    conflict_strategy: newest_wins  # newest_wins, local_wins, remote_wins, manual
    sync_dirs:
      - config
      - library
      - notes
      - reference
    exclude_patterns:
      - "*.log"
      - "*.tmp"
      - "models/*"
      - "state/*"
    manifest_path: state/sync_manifest.json"""


COMMAND = SlashCommand(
    name="sync",
    description="Manage vault synchronization. Usage: /sync [status|pull|push|manifest|diff]",
    handler=_handler,
    allow_in_planner=False,
)
