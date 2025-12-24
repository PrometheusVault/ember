"""Slash command for managing the Ember API server."""

from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.table import Table

from ..slash_commands import (
    SlashCommand,
    SlashCommandContext,
    render_rich,
)


# Global server instance (lazy initialized)
_api_server: Optional["EmberAPIServer"] = None


def _get_server(context: SlashCommandContext) -> "EmberAPIServer":
    """Get or create the API server instance."""
    global _api_server

    if _api_server is None:
        from ..api import EmberAPIServer
        from ..agents import REGISTRY

        _api_server = EmberAPIServer(
            config_bundle=context.config,
            router=context.router,
            llama_session=context.metadata.get("llama_session"),
            agent_registry=REGISTRY,
            command_history=context.metadata.get("history", []),
        )

    return _api_server


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    """Manage the Ember API server."""

    if not args:
        return _show_status(context)

    subcommand = args[0].lower()

    if subcommand == "start":
        return _start_server(context)
    elif subcommand == "stop":
        return _stop_server(context)
    elif subcommand == "status":
        return _show_status(context)
    elif subcommand == "key":
        return _show_or_regenerate_key(context, args[1:])
    elif subcommand == "help":
        return _show_help()
    else:
        return f"[api] Unknown subcommand '{subcommand}'. Use /api help for usage."


def _start_server(context: SlashCommandContext) -> str:
    """Start the API server."""
    try:
        # Check if dependencies are available
        try:
            import starlette
            import uvicorn
        except ImportError as e:
            return (
                f"[api] Missing dependencies: {e}\n"
                "Install with: pip install starlette uvicorn"
            )

        server = _get_server(context)

        if server.state.value == "running":
            return f"[api] Server is already running at http://{server.host}:{server.port}"

        success = server.start(blocking=False)

        if success:
            return (
                f"[api] Server started at http://{server.host}:{server.port}\n"
                f"API Key: {server.api_key[:8]}...{server.api_key[-8:]}\n"
                "Use /api status to check server state"
            )
        else:
            return f"[api] Failed to start server (state: {server.state.value})"

    except Exception as e:
        return f"[api] Error starting server: {e}"


def _stop_server(context: SlashCommandContext) -> str:
    """Stop the API server."""
    global _api_server

    if _api_server is None:
        return "[api] Server is not running"

    server = _api_server

    if server.state.value != "running":
        return f"[api] Server is not running (state: {server.state.value})"

    try:
        success = server.stop()
        if success:
            return "[api] Server stopped"
        else:
            return f"[api] Failed to stop server (state: {server.state.value})"
    except Exception as e:
        return f"[api] Error stopping server: {e}"


def _show_status(context: SlashCommandContext) -> str:
    """Show API server status."""
    global _api_server

    def _render(console: Console) -> None:
        table = Table(title="API Server Status", show_header=False)
        table.add_column("Property", style="bold")
        table.add_column("Value")

        if _api_server is None:
            table.add_row("State", "not initialized")
            table.add_row("URL", "-")
        else:
            status = _api_server.status()
            table.add_row("State", status["state"])
            table.add_row("Host", status["host"])
            table.add_row("Port", str(status["port"]))
            if status["url"]:
                table.add_row("URL", status["url"])

        # Show configuration
        api_config = context.config.merged.get("api", {}) if context.config.merged else {}
        table.add_row("", "")
        table.add_row("Config: enabled", str(api_config.get("enabled", False)))
        table.add_row("Config: host", api_config.get("host", "127.0.0.1"))
        table.add_row("Config: port", str(api_config.get("port", 8000)))

        console.print(table)

    return render_rich(_render)


def _show_or_regenerate_key(context: SlashCommandContext, args: List[str]) -> str:
    """Show or regenerate the API key."""
    from ..api.auth import APIKeyManager

    manager = APIKeyManager(context.config.vault_dir)

    if args and args[0].lower() == "regenerate":
        new_key = manager.regenerate_key()
        return f"[api] New API key generated: {new_key}"
    else:
        key = manager.get_or_generate_key()
        return f"[api] API Key: {key}"


def _show_help() -> str:
    """Show API command help."""
    return """[api] Usage:
  /api              Show server status
  /api start        Start the API server
  /api stop         Stop the API server
  /api status       Show server status
  /api key          Show the API key
  /api key regenerate   Generate a new API key
  /api help         Show this help

API Endpoints (when running):
  GET  /health              Health check
  GET  /api/v1/status       System status
  GET  /api/v1/agents       List agents
  POST /api/v1/agents/{name}  Trigger agent
  GET  /api/v1/config       Get configuration
  GET  /api/v1/history      Command history
  POST /api/v1/chat         Send message
  POST /api/v1/chat/stream  Stream response (SSE)
  WS   /ws/chat             WebSocket chat

Authentication:
  Include X-API-Key header or ?api_key= query param"""


COMMAND = SlashCommand(
    name="api",
    description="Manage the Ember API server. Usage: /api [start|stop|status|key|help]",
    handler=_handler,
    allow_in_planner=False,
)
