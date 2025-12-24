"""Slash command for mesh networking."""

from __future__ import annotations

import socket
from typing import List

from rich.console import Console
from rich.table import Table

from ..slash_commands import (
    SlashCommand,
    SlashCommandContext,
    render_rich,
)


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    """Manage mesh networking."""

    if not args:
        return _show_status(context)

    subcommand = args[0].lower()

    if subcommand == "status":
        return _show_status(context)
    elif subcommand == "nodes":
        return _show_nodes(context)
    elif subcommand == "discover":
        return _run_discover(context)
    elif subcommand == "ping":
        if len(args) < 2:
            return "[mesh] Usage: /mesh ping <node_id>"
        return _ping_node(context, args[1])
    elif subcommand == "start":
        return _start_mesh(context)
    elif subcommand == "stop":
        return _stop_mesh(context)
    elif subcommand == "help":
        return _show_help()
    else:
        return f"[mesh] Unknown subcommand '{subcommand}'. Use /mesh help for usage."


def _show_status(context: SlashCommandContext) -> str:
    """Show mesh status."""
    mesh_config = context.config.merged.get("mesh", {}) if context.config.merged else {}

    def _render(console: Console) -> None:
        table = Table(title="Mesh Networking Status", show_header=False)
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("Enabled", str(mesh_config.get("enabled", False)))
        table.add_row("Node ID", mesh_config.get("node_id") or "(auto)")
        table.add_row("Port", str(mesh_config.get("port", 8378)))
        table.add_row("Advertise", str(mesh_config.get("advertise", True)))
        table.add_row("TLS", str(mesh_config.get("tls", False)))
        table.add_row("Discovery Interval", f"{mesh_config.get('discovery_interval', 30)}s")

        # Capabilities
        capabilities = mesh_config.get("capabilities", ["llm"])
        table.add_row("Capabilities", ", ".join(capabilities))

        # Check if cluster is running
        cluster = context.config.agent_state.get("mesh_cluster")
        if cluster:
            status = cluster.get_status()
            table.add_row("", "")
            table.add_row("[bold]Cluster Status[/bold]", "")
            table.add_row("Local Node", cluster.local_node.node_id)
            table.add_row("Local Address", cluster.local_node.address)
            table.add_row("Nodes Online", str(status.nodes_online))
            table.add_row("Nodes Offline", str(status.nodes_offline))
            table.add_row("Uptime", f"{cluster.uptime_seconds():.0f}s")
            if status.last_discovery:
                table.add_row("Last Discovery", status.last_discovery)
        else:
            table.add_row("", "")
            table.add_row("Cluster", "[dim]Not running[/dim]")

        console.print(table)

    return render_rich(_render)


def _show_nodes(context: SlashCommandContext) -> str:
    """Show all known nodes."""
    cluster = context.config.agent_state.get("mesh_cluster")

    if not cluster:
        return "[mesh] Mesh cluster is not running. Use /mesh start to start it."

    nodes = cluster.nodes

    def _render(console: Console) -> None:
        table = Table(title=f"Mesh Nodes ({len(nodes)})")
        table.add_column("Node ID", style="cyan")
        table.add_column("Hostname")
        table.add_column("Address")
        table.add_column("Status")
        table.add_column("Capabilities")

        for node in sorted(nodes.values(), key=lambda n: n.node_id):
            status_style = "green" if node.status.value == "online" else "red"
            is_local = node.node_id == cluster.local_node.node_id

            node_id = f"{node.node_id} [dim](local)[/dim]" if is_local else node.node_id
            status = f"[{status_style}]{node.status.value}[/{status_style}]"
            caps = ", ".join(node.capabilities[:3])
            if len(node.capabilities) > 3:
                caps += f" +{len(node.capabilities) - 3}"

            table.add_row(
                node_id,
                node.hostname,
                node.address,
                status,
                caps,
            )

        console.print(table)

    return render_rich(_render)


def _run_discover(context: SlashCommandContext) -> str:
    """Run a discovery scan."""
    cluster = context.config.agent_state.get("mesh_cluster")

    if not cluster:
        return "[mesh] Mesh cluster is not running. Use /mesh start to start it."

    try:
        found = cluster.discover()
        return f"[mesh] Discovery complete: {found} nodes found"
    except Exception as e:
        return f"[mesh] Discovery failed: {e}"


def _ping_node(context: SlashCommandContext, node_id: str) -> str:
    """Ping a specific node."""
    cluster = context.config.agent_state.get("mesh_cluster")

    if not cluster:
        return "[mesh] Mesh cluster is not running. Use /mesh start to start it."

    if node_id not in cluster.remote_nodes:
        available = ", ".join(cluster.remote_nodes.keys()) or "(none)"
        return f"[mesh] Unknown node: {node_id}. Available: {available}"

    if cluster.ping_node(node_id):
        node = cluster.remote_nodes[node_id]
        return f"[mesh] Node {node_id} is online at {node.address}"
    else:
        return f"[mesh] Node {node_id} did not respond"


def _start_mesh(context: SlashCommandContext) -> str:
    """Start mesh networking."""
    mesh_config = context.config.merged.get("mesh", {}) if context.config.merged else {}

    if not mesh_config.get("enabled", False):
        return "[mesh] Mesh is disabled. Enable it in configuration first."

    # Check if already running
    if context.config.agent_state.get("mesh_cluster"):
        return "[mesh] Mesh cluster is already running"

    try:
        from ..mesh import MeshCluster, MeshSettings

        settings = MeshSettings.from_config(context.config.merged)
        hostname = socket.gethostname()

        # Get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            ip_address = "127.0.0.1"

        cluster = MeshCluster(
            settings=settings,
            hostname=hostname,
            ip_address=ip_address,
        )

        if cluster.start():
            context.config.agent_state["mesh_cluster"] = cluster
            return f"[mesh] Cluster started: {cluster.local_node.node_id} at {cluster.local_node.address}"
        else:
            return "[mesh] Failed to start cluster"

    except Exception as e:
        return f"[mesh] Error starting cluster: {e}"


def _stop_mesh(context: SlashCommandContext) -> str:
    """Stop mesh networking."""
    cluster = context.config.agent_state.get("mesh_cluster")

    if not cluster:
        return "[mesh] Mesh cluster is not running"

    try:
        cluster.stop()
        del context.config.agent_state["mesh_cluster"]
        return "[mesh] Cluster stopped"
    except Exception as e:
        return f"[mesh] Error stopping cluster: {e}"


def _show_help() -> str:
    """Show mesh command help."""
    return """[mesh] Usage:
  /mesh              Show mesh status
  /mesh status       Show mesh status
  /mesh nodes        List all known nodes
  /mesh discover     Run a discovery scan
  /mesh ping <id>    Ping a specific node
  /mesh start        Start mesh networking
  /mesh stop         Stop mesh networking
  /mesh help         Show this help

Configuration (in vault config):
  mesh:
    enabled: true
    node_id: my-node          # Auto-generated if empty
    port: 8378                # Mesh communication port
    advertise: true           # Advertise via mDNS
    capabilities:
      - llm                   # Has local LLM
      - storage               # Has vault storage
      - gateway               # Can route externally
      - sync                  # Can act as sync server
      - rag                   # Has RAG capabilities
    tls: false                # Use TLS (requires certs)
    discovery_interval: 30    # Seconds between discovery scans
    health_check_interval: 60 # Seconds between health checks
    node_timeout: 120         # Seconds before node marked offline

Optional dependencies:
  pip install zeroconf  # For mDNS discovery (recommended)"""


COMMAND = SlashCommand(
    name="mesh",
    description="Manage mesh networking. Usage: /mesh [status|nodes|discover|ping|start|stop]",
    handler=_handler,
    allow_in_planner=False,
)
