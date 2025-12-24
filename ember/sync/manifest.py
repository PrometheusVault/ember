"""Vault manifest generation and management."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

logger = logging.getLogger("ember.sync.manifest")


@dataclass
class FileInfo:
    """Information about a single file in the vault."""

    path: str  # Relative path from vault root
    hash: str  # SHA-256 hash of content
    size: int  # File size in bytes
    mtime: float  # Modification time (Unix timestamp)
    mode: int = 0o644  # File permissions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "hash": self.hash,
            "size": self.size,
            "mtime": self.mtime,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileInfo":
        return cls(
            path=data["path"],
            hash=data["hash"],
            size=data["size"],
            mtime=data["mtime"],
            mode=data.get("mode", 0o644),
        )


@dataclass
class VaultManifest:
    """Complete manifest of vault contents for synchronization."""

    node_id: str
    vault_dir: Path
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    files: Dict[str, FileInfo] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "vault_dir": str(self.vault_dir),
            "version": self.version,
            "created_at": self.created_at,
            "files": {path: info.to_dict() for path, info in self.files.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VaultManifest":
        manifest = cls(
            node_id=data["node_id"],
            vault_dir=Path(data["vault_dir"]),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", ""),
        )
        for path, info_data in data.get("files", {}).items():
            manifest.files[path] = FileInfo.from_dict(info_data)
        return manifest

    def save(self, path: Path) -> None:
        """Save manifest to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.debug("Saved manifest to %s (%d files)", path, len(self.files))

    @classmethod
    def load(cls, path: Path) -> Optional["VaultManifest"]:
        """Load manifest from a JSON file."""
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to load manifest from %s: %s", path, e)
            return None


class ManifestBuilder:
    """Builds vault manifests by scanning directories."""

    def __init__(
        self,
        vault_dir: Path,
        node_id: str,
        sync_dirs: Optional[Sequence[str]] = None,
        exclude_patterns: Optional[Sequence[str]] = None,
    ):
        self.vault_dir = vault_dir
        self.node_id = node_id
        self.sync_dirs = list(sync_dirs) if sync_dirs else ["config", "library", "notes"]
        self.exclude_patterns = list(exclude_patterns) if exclude_patterns else []

    def build(self) -> VaultManifest:
        """Build a manifest by scanning the vault."""
        manifest = VaultManifest(
            node_id=self.node_id,
            vault_dir=self.vault_dir,
        )

        for file_path in self._iter_files():
            try:
                info = self._get_file_info(file_path)
                manifest.files[info.path] = info
            except OSError as e:
                logger.warning("Failed to read file %s: %s", file_path, e)

        logger.info("Built manifest with %d files", len(manifest.files))
        return manifest

    def _iter_files(self) -> Iterator[Path]:
        """Iterate over all syncable files in the vault."""
        for sync_dir in self.sync_dirs:
            dir_path = self.vault_dir / sync_dir
            if not dir_path.exists():
                continue

            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue

                rel_path = str(file_path.relative_to(self.vault_dir))
                if self._is_excluded(rel_path):
                    continue

                yield file_path

    def _is_excluded(self, rel_path: str) -> bool:
        """Check if a path matches any exclude pattern."""
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            # Also check just the filename
            if fnmatch.fnmatch(Path(rel_path).name, pattern):
                return True
        return False

    def _get_file_info(self, file_path: Path) -> FileInfo:
        """Get file info including hash."""
        stat = file_path.stat()
        rel_path = str(file_path.relative_to(self.vault_dir))

        # Calculate SHA-256 hash
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)

        return FileInfo(
            path=rel_path,
            hash=hasher.hexdigest(),
            size=stat.st_size,
            mtime=stat.st_mtime,
            mode=stat.st_mode & 0o777,
        )


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


__all__ = ["VaultManifest", "FileInfo", "ManifestBuilder", "compute_file_hash"]
