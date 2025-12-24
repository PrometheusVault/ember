"""Node representation for mesh networking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeStatus(str, Enum):
    """Status of a mesh node."""
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    CONNECTING = "connecting"


class NodeCapability(str, Enum):
    """Capabilities a node can advertise."""
    LLM = "llm"              # Has local LLM
    STORAGE = "storage"      # Has vault storage
    GATEWAY = "gateway"      # Can route to external networks
    SYNC = "sync"            # Can act as sync server
    RAG = "rag"              # Has RAG capabilities


@dataclass
class NodeInfo:
    """Information about a mesh node."""

    node_id: str
    hostname: str
    ip_address: str
    port: int
    capabilities: List[str] = field(default_factory=list)
    version: str = ""
    status: NodeStatus = NodeStatus.UNKNOWN
    last_seen: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "port": self.port,
            "capabilities": self.capabilities,
            "version": self.version,
            "status": self.status.value,
            "last_seen": self.last_seen,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeInfo":
        return cls(
            node_id=data["node_id"],
            hostname=data["hostname"],
            ip_address=data["ip_address"],
            port=data["port"],
            capabilities=data.get("capabilities", []),
            version=data.get("version", ""),
            status=NodeStatus(data.get("status", "unknown")),
            last_seen=data.get("last_seen"),
            metadata=data.get("metadata", {}),
        )

    @property
    def address(self) -> str:
        """Get the full address for this node."""
        return f"{self.ip_address}:{self.port}"

    @property
    def url(self) -> str:
        """Get the HTTP URL for this node."""
        return f"http://{self.ip_address}:{self.port}"

    def has_capability(self, capability: str) -> bool:
        """Check if node has a specific capability."""
        return capability in self.capabilities


def generate_node_id() -> str:
    """Generate a unique node ID."""
    return str(uuid.uuid4())[:8]


def get_local_node_info(
    node_id: str,
    hostname: str,
    ip_address: str,
    port: int,
    capabilities: Optional[List[str]] = None,
    version: str = "1.0.0",
) -> NodeInfo:
    """Create a NodeInfo for the local node."""
    return NodeInfo(
        node_id=node_id,
        hostname=hostname,
        ip_address=ip_address,
        port=port,
        capabilities=capabilities or [NodeCapability.LLM.value],
        version=version,
        status=NodeStatus.ONLINE,
    )


__all__ = [
    "NodeStatus",
    "NodeCapability",
    "NodeInfo",
    "generate_node_id",
    "get_local_node_info",
]
