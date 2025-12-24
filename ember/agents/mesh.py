"""Mesh networking agent for node discovery and cluster management."""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from ..configuration import ConfigurationBundle

logger = logging.getLogger("ember.agents.mesh")


@dataclass
class MeshAgentResult:
    """Summary data returned after the mesh agent runs."""

    status: Literal["ok", "disabled", "error", "pending"]
    detail: str
    node_id: str = ""
    local_address: str = ""
    nodes_discovered: int = 0
    capabilities: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "node_id": self.node_id,
            "local_address": self.local_address,
            "nodes_discovered": self.nodes_discovered,
            "capabilities": self.capabilities,
            "errors": self.errors,
        }


def _get_local_ip() -> str:
    """Get the local IP address."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def run_mesh_agent(bundle: ConfigurationBundle) -> MeshAgentResult:
    """Initialize mesh networking and discover nodes."""

    mesh_config = bundle.merged.get("mesh", {}) if bundle.merged else {}
    enabled = bool(mesh_config.get("enabled", False))

    if not enabled:
        detail = "mesh.agent disabled via configuration."
        logger.info(detail)
        return MeshAgentResult(status="disabled", detail=detail)

    try:
        from ..mesh import MeshCluster, MeshSettings

        settings = MeshSettings.from_config(bundle.merged)

        # Get local network info
        hostname = socket.gethostname()
        ip_address = _get_local_ip()

        # Create and start cluster
        cluster = MeshCluster(
            settings=settings,
            hostname=hostname,
            ip_address=ip_address,
        )

        if not cluster.start():
            return MeshAgentResult(
                status="error",
                detail="Failed to start mesh cluster",
            )

        # Perform initial discovery
        nodes_found = cluster.discover()

        # Get cluster status
        status = cluster.get_status()

        detail = f"Node {cluster.local_node.node_id} online, {nodes_found} nodes discovered"

        result = MeshAgentResult(
            status="ok",
            detail=detail,
            node_id=cluster.local_node.node_id,
            local_address=cluster.local_node.address,
            nodes_discovered=nodes_found,
            capabilities=settings.capabilities,
        )

        # Store cluster reference for later use
        bundle.agent_state["mesh_cluster"] = cluster

        logger.info("mesh.agent completed: %s", detail)
        return result

    except ImportError as e:
        detail = f"Mesh dependencies not available: {e}"
        logger.error(detail)
        return MeshAgentResult(
            status="error",
            detail=detail,
            errors=[str(e)],
        )

    except Exception as e:
        detail = f"Mesh agent error: {e}"
        logger.exception(detail)
        return MeshAgentResult(
            status="error",
            detail=detail,
            errors=[str(e)],
        )


__all__ = ["run_mesh_agent", "MeshAgentResult"]
