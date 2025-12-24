"""Cluster management for mesh networking."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .discovery import DiscoverySettings, MeshDiscovery
from .node import NodeCapability, NodeInfo, NodeStatus, generate_node_id
from .protocol import MeshProtocol

logger = logging.getLogger("ember.mesh.cluster")


@dataclass
class MeshSettings:
    """Settings for mesh cluster."""

    enabled: bool = False
    node_id: str = ""
    port: int = 8378
    advertise: bool = True
    capabilities: List[str] = field(default_factory=lambda: ["llm"])
    tls: bool = False
    discovery_interval: int = 30
    health_check_interval: int = 60
    node_timeout: int = 120

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "MeshSettings":
        raw = config.get("mesh", {}) if config else {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            node_id=str(raw.get("node_id", "")),
            port=int(raw.get("port", 8378)),
            advertise=bool(raw.get("advertise", True)),
            capabilities=list(raw.get("capabilities", ["llm"])),
            tls=bool(raw.get("tls", False)),
            discovery_interval=int(raw.get("discovery_interval", 30)),
            health_check_interval=int(raw.get("health_check_interval", 60)),
            node_timeout=int(raw.get("node_timeout", 120)),
        )


@dataclass
class ClusterStatus:
    """Status of the mesh cluster."""

    local_node: Optional[NodeInfo] = None
    nodes_online: int = 0
    nodes_offline: int = 0
    total_nodes: int = 0
    capabilities: Dict[str, int] = field(default_factory=dict)
    last_discovery: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_node": self.local_node.to_dict() if self.local_node else None,
            "nodes_online": self.nodes_online,
            "nodes_offline": self.nodes_offline,
            "total_nodes": self.total_nodes,
            "capabilities": self.capabilities,
            "last_discovery": self.last_discovery,
        }


class MeshCluster:
    """Manages the mesh cluster of Ember nodes."""

    def __init__(
        self,
        settings: MeshSettings,
        hostname: str,
        ip_address: str,
        version: str = "1.0.0",
        on_node_joined: Optional[Callable[[NodeInfo], None]] = None,
        on_node_left: Optional[Callable[[str], None]] = None,
    ):
        self.settings = settings
        self.version = version
        self.on_node_joined = on_node_joined
        self.on_node_left = on_node_left

        # Generate or use configured node ID
        node_id = settings.node_id or generate_node_id()

        # Create local node info
        self.local_node = NodeInfo(
            node_id=node_id,
            hostname=hostname,
            ip_address=ip_address,
            port=settings.port,
            capabilities=settings.capabilities,
            version=version,
            status=NodeStatus.ONLINE,
        )

        # Initialize components
        discovery_settings = DiscoverySettings(
            enabled=settings.enabled,
            port=settings.port,
            advertise=settings.advertise,
            discovery_interval=settings.discovery_interval,
        )

        self._discovery = MeshDiscovery(
            local_node=self.local_node,
            settings=discovery_settings,
            on_node_found=self._handle_node_found,
            on_node_lost=self._handle_node_lost,
        )

        self._protocol = MeshProtocol(self.local_node)

        self._nodes: Dict[str, NodeInfo] = {}
        self._running = False
        self._health_thread: Optional[threading.Thread] = None
        self._start_time = datetime.now(timezone.utc)
        self._last_discovery: Optional[str] = None

    @property
    def nodes(self) -> Dict[str, NodeInfo]:
        """Get all known nodes including local."""
        all_nodes = {self.local_node.node_id: self.local_node}
        all_nodes.update(self._nodes)
        return all_nodes

    @property
    def remote_nodes(self) -> Dict[str, NodeInfo]:
        """Get only remote nodes."""
        return dict(self._nodes)

    def start(self) -> bool:
        """Start the mesh cluster."""
        if self._running:
            return True

        if not self.settings.enabled:
            logger.info("Mesh networking is disabled")
            return False

        # Start discovery
        if not self._discovery.start():
            logger.error("Failed to start mesh discovery")
            return False

        # Start health check thread
        self._running = True
        self._health_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
        )
        self._health_thread.start()

        logger.info("Mesh cluster started: %s", self.local_node.node_id)
        return True

    def stop(self) -> None:
        """Stop the mesh cluster."""
        self._running = False

        self._discovery.stop()

        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=2.0)

        logger.info("Mesh cluster stopped")

    def discover(self) -> int:
        """Trigger manual discovery."""
        result = self._discovery.discover_once()
        self._last_discovery = datetime.now(timezone.utc).isoformat()
        return result.nodes_found

    def ping_node(self, node_id: str) -> bool:
        """Ping a specific node."""
        if node_id not in self._nodes:
            return False

        node = self._nodes[node_id]
        response = self._protocol.ping(node)

        if response:
            node.status = NodeStatus.ONLINE
            node.last_seen = datetime.now(timezone.utc).isoformat()
            return True
        else:
            node.status = NodeStatus.OFFLINE
            return False

    def get_nodes_with_capability(self, capability: str) -> List[NodeInfo]:
        """Get all nodes with a specific capability."""
        return [
            node for node in self._nodes.values()
            if node.has_capability(capability) and node.status == NodeStatus.ONLINE
        ]

    def get_status(self) -> ClusterStatus:
        """Get cluster status."""
        online = sum(1 for n in self._nodes.values() if n.status == NodeStatus.ONLINE)
        offline = sum(1 for n in self._nodes.values() if n.status == NodeStatus.OFFLINE)

        # Count capabilities
        capabilities: Dict[str, int] = {}
        for node in self._nodes.values():
            if node.status == NodeStatus.ONLINE:
                for cap in node.capabilities:
                    capabilities[cap] = capabilities.get(cap, 0) + 1

        # Include local node capabilities
        for cap in self.local_node.capabilities:
            capabilities[cap] = capabilities.get(cap, 0) + 1

        return ClusterStatus(
            local_node=self.local_node,
            nodes_online=online + 1,  # Include local node
            nodes_offline=offline,
            total_nodes=len(self._nodes) + 1,
            capabilities=capabilities,
            last_discovery=self._last_discovery,
        )

    def uptime_seconds(self) -> float:
        """Get cluster uptime in seconds."""
        delta = datetime.now(timezone.utc) - self._start_time
        return delta.total_seconds()

    def _handle_node_found(self, node: NodeInfo) -> None:
        """Handle a newly discovered node."""
        is_new = node.node_id not in self._nodes
        self._nodes[node.node_id] = node

        if is_new:
            logger.info("Node joined cluster: %s (%s)", node.node_id, node.address)
            if self.on_node_joined:
                self.on_node_joined(node)

    def _handle_node_lost(self, node_id: str) -> None:
        """Handle a node leaving the cluster."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            logger.info("Node left cluster: %s", node_id)
            if self.on_node_left:
                self.on_node_left(node_id)

    def _health_check_loop(self) -> None:
        """Background loop for health checking nodes."""
        while self._running:
            try:
                self._check_node_health()
            except Exception as e:
                logger.error("Health check error: %s", e)

            # Wait for next interval
            for _ in range(self.settings.health_check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _check_node_health(self) -> None:
        """Check health of all known nodes."""
        now = datetime.now(timezone.utc)

        for node_id, node in list(self._nodes.items()):
            # Skip if recently seen
            if node.last_seen:
                try:
                    last_seen = datetime.fromisoformat(node.last_seen.replace("Z", "+00:00"))
                    age = (now - last_seen).total_seconds()

                    if age < self.settings.health_check_interval:
                        continue

                    if age > self.settings.node_timeout:
                        node.status = NodeStatus.OFFLINE
                        continue

                except Exception:
                    pass

            # Ping the node
            self.ping_node(node_id)


__all__ = ["MeshCluster", "MeshSettings", "ClusterStatus"]
