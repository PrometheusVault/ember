"""Node discovery for mesh networking using mDNS/Avahi."""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .node import NodeInfo, NodeStatus

logger = logging.getLogger("ember.mesh.discovery")

# Service type for Ember mesh nodes
SERVICE_TYPE = "_ember._tcp.local."
SERVICE_NAME_PREFIX = "ember-node-"


@dataclass
class DiscoverySettings:
    """Settings for mesh discovery."""

    enabled: bool = True
    port: int = 8378
    advertise: bool = True
    discovery_interval: int = 30
    service_type: str = SERVICE_TYPE


@dataclass
class DiscoveryResult:
    """Result of a discovery operation."""

    nodes_found: int = 0
    nodes: List[NodeInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class MeshDiscovery:
    """Discovers other Ember nodes on the local network."""

    def __init__(
        self,
        local_node: NodeInfo,
        settings: DiscoverySettings,
        on_node_found: Optional[Callable[[NodeInfo], None]] = None,
        on_node_lost: Optional[Callable[[str], None]] = None,
    ):
        self.local_node = local_node
        self.settings = settings
        self.on_node_found = on_node_found
        self.on_node_lost = on_node_lost

        self._known_nodes: Dict[str, NodeInfo] = {}
        self._running = False
        self._discovery_thread: Optional[threading.Thread] = None
        self._zeroconf = None
        self._service_info = None

    @property
    def known_nodes(self) -> Dict[str, NodeInfo]:
        """Get all known nodes."""
        return dict(self._known_nodes)

    def start(self) -> bool:
        """Start discovery and optionally advertise the local node."""
        if self._running:
            return True

        try:
            # Try to use zeroconf for mDNS
            from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf

            self._zeroconf = Zeroconf()

            # Advertise local node
            if self.settings.advertise:
                self._advertise_node()

            # Start browsing for other nodes
            self._browser = ServiceBrowser(
                self._zeroconf,
                self.settings.service_type,
                self,
            )

            self._running = True
            logger.info("Mesh discovery started with mDNS")
            return True

        except ImportError:
            logger.warning("zeroconf not available, using fallback discovery")
            return self._start_fallback_discovery()

        except Exception as e:
            logger.error("Failed to start mesh discovery: %s", e)
            return False

    def stop(self) -> None:
        """Stop discovery and unadvertise."""
        self._running = False

        if self._zeroconf:
            try:
                if self._service_info:
                    self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
            except Exception as e:
                logger.warning("Error stopping zeroconf: %s", e)
            self._zeroconf = None

        if self._discovery_thread and self._discovery_thread.is_alive():
            self._discovery_thread.join(timeout=2.0)

        logger.info("Mesh discovery stopped")

    def discover_once(self) -> DiscoveryResult:
        """Perform a single discovery scan."""
        result = DiscoveryResult()

        # Use broadcast UDP for simple discovery
        try:
            discovered = self._udp_discovery_scan()
            result.nodes = discovered
            result.nodes_found = len(discovered)

            for node in discovered:
                if node.node_id != self.local_node.node_id:
                    self._add_node(node)

        except Exception as e:
            result.errors.append(str(e))
            logger.error("Discovery scan failed: %s", e)

        return result

    def _advertise_node(self) -> None:
        """Advertise the local node via mDNS."""
        try:
            from zeroconf import ServiceInfo

            properties = {
                b"node_id": self.local_node.node_id.encode(),
                b"version": self.local_node.version.encode(),
                b"capabilities": ",".join(self.local_node.capabilities).encode(),
            }

            self._service_info = ServiceInfo(
                self.settings.service_type,
                f"{SERVICE_NAME_PREFIX}{self.local_node.node_id}.{self.settings.service_type}",
                addresses=[socket.inet_aton(self.local_node.ip_address)],
                port=self.settings.port,
                properties=properties,
                server=f"{self.local_node.hostname}.local.",
            )

            self._zeroconf.register_service(self._service_info)
            logger.info("Advertising node %s on port %d", self.local_node.node_id, self.settings.port)

        except Exception as e:
            logger.error("Failed to advertise node: %s", e)

    def _start_fallback_discovery(self) -> bool:
        """Start fallback discovery using UDP broadcast."""
        self._running = True
        self._discovery_thread = threading.Thread(
            target=self._fallback_discovery_loop,
            daemon=True,
        )
        self._discovery_thread.start()
        logger.info("Mesh discovery started with UDP fallback")
        return True

    def _fallback_discovery_loop(self) -> None:
        """Background loop for fallback discovery."""
        while self._running:
            try:
                self.discover_once()
            except Exception as e:
                logger.error("Fallback discovery error: %s", e)

            # Wait for next interval
            for _ in range(self.settings.discovery_interval):
                if not self._running:
                    break
                time.sleep(1)

    def _udp_discovery_scan(self) -> List[NodeInfo]:
        """Scan for nodes using UDP broadcast."""
        discovered = []

        try:
            # Create UDP socket for broadcast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2.0)

            # Send discovery request
            request = json.dumps({
                "type": "discover",
                "node_id": self.local_node.node_id,
            }).encode()

            sock.sendto(request, ("<broadcast>", self.settings.port))

            # Collect responses
            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = json.loads(data.decode())

                    if response.get("type") == "announce" and "node_info" in response:
                        node = NodeInfo.from_dict(response["node_info"])
                        if node.node_id != self.local_node.node_id:
                            discovered.append(node)

                except socket.timeout:
                    break

            sock.close()

        except Exception as e:
            logger.debug("UDP discovery scan error: %s", e)

        return discovered

    def _add_node(self, node: NodeInfo) -> None:
        """Add a discovered node."""
        node.status = NodeStatus.ONLINE
        is_new = node.node_id not in self._known_nodes
        self._known_nodes[node.node_id] = node

        if is_new and self.on_node_found:
            self.on_node_found(node)

    def _remove_node(self, node_id: str) -> None:
        """Remove a node that is no longer available."""
        if node_id in self._known_nodes:
            del self._known_nodes[node_id]
            if self.on_node_lost:
                self.on_node_lost(node_id)

    # ServiceListener callbacks for zeroconf
    def add_service(self, zc, service_type: str, name: str) -> None:
        """Called when a new service is discovered."""
        try:
            from zeroconf import ServiceInfo

            info = zc.get_service_info(service_type, name)
            if info:
                node = self._parse_service_info(info)
                if node and node.node_id != self.local_node.node_id:
                    self._add_node(node)
                    logger.info("Discovered node: %s at %s", node.node_id, node.address)

        except Exception as e:
            logger.error("Error processing service: %s", e)

    def remove_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is removed."""
        # Extract node_id from service name
        if name.startswith(SERVICE_NAME_PREFIX):
            node_id = name[len(SERVICE_NAME_PREFIX):].split(".")[0]
            self._remove_node(node_id)
            logger.info("Node removed: %s", node_id)

    def update_service(self, zc, service_type: str, name: str) -> None:
        """Called when a service is updated."""
        self.add_service(zc, service_type, name)

    def _parse_service_info(self, info) -> Optional[NodeInfo]:
        """Parse a ServiceInfo into a NodeInfo."""
        try:
            properties = info.properties or {}
            node_id = properties.get(b"node_id", b"").decode()

            if not node_id:
                return None

            # Get address
            addresses = info.parsed_addresses()
            if not addresses:
                return None

            capabilities_str = properties.get(b"capabilities", b"").decode()
            capabilities = capabilities_str.split(",") if capabilities_str else []

            return NodeInfo(
                node_id=node_id,
                hostname=info.server.rstrip("."),
                ip_address=addresses[0],
                port=info.port,
                capabilities=capabilities,
                version=properties.get(b"version", b"").decode(),
                status=NodeStatus.ONLINE,
            )

        except Exception as e:
            logger.error("Failed to parse service info: %s", e)
            return None


__all__ = ["MeshDiscovery", "DiscoverySettings", "DiscoveryResult"]
