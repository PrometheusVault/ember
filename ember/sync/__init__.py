"""Vault synchronization module for Ember."""

from __future__ import annotations

from .manifest import VaultManifest, FileInfo, ManifestBuilder, compute_file_hash
from .protocol import SyncDelta, SyncRequest, SyncResponse, SyncAction, FileChange, compute_delta
from .client import SyncClient, SyncSettings, SyncResult
from .conflict import ConflictResolver, ConflictStrategy, ConflictResolution

__all__ = [
    # Manifest
    "VaultManifest",
    "FileInfo",
    "ManifestBuilder",
    "compute_file_hash",
    # Protocol
    "SyncDelta",
    "SyncRequest",
    "SyncResponse",
    "SyncAction",
    "FileChange",
    "compute_delta",
    # Client
    "SyncClient",
    "SyncSettings",
    "SyncResult",
    # Conflict
    "ConflictResolver",
    "ConflictStrategy",
    "ConflictResolution",
]
