"""Protocol definitions for mesh node communication."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .node import NodeInfo


class MessageType(str, Enum):
    """Types of mesh messages."""
    PING = "ping"
    PONG = "pong"
    ANNOUNCE = "announce"
    QUERY = "query"
    RESPONSE = "response"
    REQUEST = "request"
    ERROR = "error"


@dataclass
class MeshMessage:
    """A message exchanged between mesh nodes."""

    type: MessageType
    source_node: str
    target_node: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message_id: str = ""

    def __post_init__(self):
        if not self.message_id:
            import uuid
            self.message_id = str(uuid.uuid4())[:12]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MeshMessage":
        return cls(
            type=MessageType(data["type"]),
            source_node=data["source_node"],
            target_node=data.get("target_node"),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
            message_id=data.get("message_id", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "MeshMessage":
        return cls.from_dict(json.loads(json_str))


@dataclass
class PingRequest:
    """Request to check if a node is alive."""
    source_node: str
    capabilities: List[str] = field(default_factory=list)

    def to_message(self) -> MeshMessage:
        return MeshMessage(
            type=MessageType.PING,
            source_node=self.source_node,
            payload={"capabilities": self.capabilities},
        )


@dataclass
class PongResponse:
    """Response to a ping request."""
    node_info: NodeInfo
    uptime_seconds: float = 0.0

    def to_message(self, target_node: str) -> MeshMessage:
        return MeshMessage(
            type=MessageType.PONG,
            source_node=self.node_info.node_id,
            target_node=target_node,
            payload={
                "node_info": self.node_info.to_dict(),
                "uptime_seconds": self.uptime_seconds,
            },
        )


@dataclass
class NodeAnnouncement:
    """Announcement of node presence on the mesh."""
    node_info: NodeInfo

    def to_message(self) -> MeshMessage:
        return MeshMessage(
            type=MessageType.ANNOUNCE,
            source_node=self.node_info.node_id,
            payload={"node_info": self.node_info.to_dict()},
        )


class MeshProtocol:
    """Protocol handler for mesh communication."""

    def __init__(self, local_node: NodeInfo, timeout: float = 5.0):
        self.local_node = local_node
        self.timeout = timeout

    def ping(self, target: NodeInfo) -> Optional[PongResponse]:
        """Send a ping to a target node and wait for response."""
        request = PingRequest(
            source_node=self.local_node.node_id,
            capabilities=self.local_node.capabilities,
        )

        message = request.to_message()
        message.target_node = target.node_id

        try:
            response = self._send_message(target.url, message)
            if response and response.type == MessageType.PONG:
                node_info = NodeInfo.from_dict(response.payload["node_info"])
                return PongResponse(
                    node_info=node_info,
                    uptime_seconds=response.payload.get("uptime_seconds", 0),
                )
        except Exception:
            pass

        return None

    def announce(self, targets: List[NodeInfo]) -> int:
        """Announce presence to multiple nodes."""
        announcement = NodeAnnouncement(node_info=self.local_node)
        message = announcement.to_message()

        successful = 0
        for target in targets:
            try:
                self._send_message(target.url, message, expect_response=False)
                successful += 1
            except Exception:
                continue

        return successful

    def send_request(
        self,
        target: NodeInfo,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[MeshMessage]:
        """Send a request to a target node."""
        message = MeshMessage(
            type=MessageType.REQUEST,
            source_node=self.local_node.node_id,
            target_node=target.node_id,
            payload={
                "action": action,
                "params": params or {},
            },
        )

        try:
            return self._send_message(target.url, message)
        except Exception:
            return None

    def _send_message(
        self,
        url: str,
        message: MeshMessage,
        expect_response: bool = True,
    ) -> Optional[MeshMessage]:
        """Send a message to a node's mesh endpoint."""
        endpoint = f"{url.rstrip('/')}/mesh/message"
        data = message.to_json().encode("utf-8")

        req = Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                if expect_response and resp.status == 200:
                    response_data = resp.read().decode("utf-8")
                    return MeshMessage.from_json(response_data)
        except (HTTPError, URLError):
            raise

        return None


__all__ = [
    "MessageType",
    "MeshMessage",
    "PingRequest",
    "PongResponse",
    "NodeAnnouncement",
    "MeshProtocol",
]
