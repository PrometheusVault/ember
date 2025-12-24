"""Sync protocol data structures."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manifest import FileInfo, VaultManifest


class SyncAction(str, Enum):
    """Actions that can be taken during sync."""
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    CONFLICT = "conflict"
    SKIP = "skip"


@dataclass
class FileChange:
    """Represents a change to a single file."""

    path: str
    action: SyncAction
    local_info: Optional[FileInfo] = None
    remote_info: Optional[FileInfo] = None
    content: Optional[bytes] = None  # For ADD/UPDATE actions

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "path": self.path,
            "action": self.action.value,
        }
        if self.local_info:
            result["local_info"] = self.local_info.to_dict()
        if self.remote_info:
            result["remote_info"] = self.remote_info.to_dict()
        if self.content:
            result["content"] = base64.b64encode(self.content).decode("ascii")
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileChange":
        content = None
        if "content" in data:
            content = base64.b64decode(data["content"])

        return cls(
            path=data["path"],
            action=SyncAction(data["action"]),
            local_info=FileInfo.from_dict(data["local_info"]) if data.get("local_info") else None,
            remote_info=FileInfo.from_dict(data["remote_info"]) if data.get("remote_info") else None,
            content=content,
        )


@dataclass
class SyncDelta:
    """Computed differences between two manifests."""

    local_node: str
    remote_node: str
    to_upload: List[FileChange] = field(default_factory=list)
    to_download: List[FileChange] = field(default_factory=list)
    conflicts: List[FileChange] = field(default_factory=list)
    to_delete_local: List[FileChange] = field(default_factory=list)
    to_delete_remote: List[FileChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.to_upload or self.to_download or self.conflicts
            or self.to_delete_local or self.to_delete_remote
        )

    @property
    def total_changes(self) -> int:
        return (
            len(self.to_upload) + len(self.to_download) + len(self.conflicts)
            + len(self.to_delete_local) + len(self.to_delete_remote)
        )

    def summary(self) -> str:
        parts = []
        if self.to_upload:
            parts.append(f"{len(self.to_upload)} to upload")
        if self.to_download:
            parts.append(f"{len(self.to_download)} to download")
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflicts")
        if self.to_delete_local:
            parts.append(f"{len(self.to_delete_local)} to delete locally")
        if self.to_delete_remote:
            parts.append(f"{len(self.to_delete_remote)} to delete remotely")
        return ", ".join(parts) if parts else "no changes"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_node": self.local_node,
            "remote_node": self.remote_node,
            "to_upload": [c.to_dict() for c in self.to_upload],
            "to_download": [c.to_dict() for c in self.to_download],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "to_delete_local": [c.to_dict() for c in self.to_delete_local],
            "to_delete_remote": [c.to_dict() for c in self.to_delete_remote],
        }


@dataclass
class SyncRequest:
    """Request sent to initiate or continue a sync operation."""

    node_id: str
    manifest: VaultManifest
    request_type: str = "full"  # "full", "delta", "pull", "push"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "manifest": self.manifest.to_dict(),
            "request_type": self.request_type,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncRequest":
        return cls(
            node_id=data["node_id"],
            manifest=VaultManifest.from_dict(data["manifest"]),
            request_type=data.get("request_type", "full"),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class SyncResponse:
    """Response from a sync operation."""

    status: str  # "ok", "error", "conflict"
    node_id: str
    delta: Optional[SyncDelta] = None
    files: List[FileChange] = field(default_factory=list)
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status,
            "node_id": self.node_id,
            "message": self.message,
            "timestamp": self.timestamp,
        }
        if self.delta:
            result["delta"] = self.delta.to_dict()
        if self.files:
            result["files"] = [f.to_dict() for f in self.files]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncResponse":
        delta = None
        if "delta" in data:
            delta_data = data["delta"]
            delta = SyncDelta(
                local_node=delta_data["local_node"],
                remote_node=delta_data["remote_node"],
            )
            # Parse changes
            for change_data in delta_data.get("to_upload", []):
                delta.to_upload.append(FileChange.from_dict(change_data))
            for change_data in delta_data.get("to_download", []):
                delta.to_download.append(FileChange.from_dict(change_data))
            for change_data in delta_data.get("conflicts", []):
                delta.conflicts.append(FileChange.from_dict(change_data))

        files = [FileChange.from_dict(f) for f in data.get("files", [])]

        return cls(
            status=data["status"],
            node_id=data["node_id"],
            delta=delta,
            files=files,
            message=data.get("message", ""),
            timestamp=data.get("timestamp", ""),
        )


def compute_delta(
    local_manifest: VaultManifest,
    remote_manifest: VaultManifest,
) -> SyncDelta:
    """Compute the delta between local and remote manifests."""
    delta = SyncDelta(
        local_node=local_manifest.node_id,
        remote_node=remote_manifest.node_id,
    )

    local_paths = set(local_manifest.files.keys())
    remote_paths = set(remote_manifest.files.keys())

    # Files only in local (to upload)
    for path in local_paths - remote_paths:
        delta.to_upload.append(FileChange(
            path=path,
            action=SyncAction.ADD,
            local_info=local_manifest.files[path],
        ))

    # Files only in remote (to download)
    for path in remote_paths - local_paths:
        delta.to_download.append(FileChange(
            path=path,
            action=SyncAction.ADD,
            remote_info=remote_manifest.files[path],
        ))

    # Files in both (check for changes)
    for path in local_paths & remote_paths:
        local_info = local_manifest.files[path]
        remote_info = remote_manifest.files[path]

        if local_info.hash == remote_info.hash:
            # Same content, no change needed
            continue

        # Content differs - determine direction based on mtime
        if local_info.mtime > remote_info.mtime:
            # Local is newer - upload
            delta.to_upload.append(FileChange(
                path=path,
                action=SyncAction.UPDATE,
                local_info=local_info,
                remote_info=remote_info,
            ))
        elif remote_info.mtime > local_info.mtime:
            # Remote is newer - download
            delta.to_download.append(FileChange(
                path=path,
                action=SyncAction.UPDATE,
                local_info=local_info,
                remote_info=remote_info,
            ))
        else:
            # Same mtime but different hash - conflict
            delta.conflicts.append(FileChange(
                path=path,
                action=SyncAction.CONFLICT,
                local_info=local_info,
                remote_info=remote_info,
            ))

    return delta


__all__ = [
    "SyncAction",
    "FileChange",
    "SyncDelta",
    "SyncRequest",
    "SyncResponse",
    "compute_delta",
]
