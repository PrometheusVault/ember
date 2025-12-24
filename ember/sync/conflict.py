"""Conflict resolution strategies for vault synchronization."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .protocol import FileChange, SyncAction

logger = logging.getLogger("ember.sync.conflict")


class ConflictStrategy(str, Enum):
    """Strategies for resolving sync conflicts."""
    NEWEST_WINS = "newest_wins"
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    MANUAL = "manual"
    BACKUP_BOTH = "backup_both"


@dataclass
class ConflictResolution:
    """Result of conflict resolution."""

    change: FileChange
    action: str  # "use_local", "use_remote", "skip", "backup"
    backup_path: Optional[Path] = None
    message: str = ""


class ConflictResolver:
    """Resolves file conflicts during synchronization."""

    def __init__(
        self,
        vault_dir: Path,
        strategy: ConflictStrategy = ConflictStrategy.NEWEST_WINS,
        backup_dir: Optional[Path] = None,
    ):
        self.vault_dir = vault_dir
        self.strategy = strategy
        self.backup_dir = backup_dir or vault_dir / ".sync_backups"

    def resolve(self, change: FileChange) -> ConflictResolution:
        """Resolve a single conflict based on the configured strategy."""
        if change.action != SyncAction.CONFLICT:
            return ConflictResolution(
                change=change,
                action="skip",
                message="Not a conflict",
            )

        if self.strategy == ConflictStrategy.NEWEST_WINS:
            return self._resolve_newest_wins(change)
        elif self.strategy == ConflictStrategy.LOCAL_WINS:
            return self._resolve_local_wins(change)
        elif self.strategy == ConflictStrategy.REMOTE_WINS:
            return self._resolve_remote_wins(change)
        elif self.strategy == ConflictStrategy.BACKUP_BOTH:
            return self._resolve_backup_both(change)
        else:  # MANUAL
            return self._resolve_manual(change)

    def _resolve_newest_wins(self, change: FileChange) -> ConflictResolution:
        """Use whichever version has the newer modification time."""
        local_mtime = change.local_info.mtime if change.local_info else 0
        remote_mtime = change.remote_info.mtime if change.remote_info else 0

        if local_mtime >= remote_mtime:
            return ConflictResolution(
                change=change,
                action="use_local",
                message=f"Local is newer ({local_mtime} >= {remote_mtime})",
            )
        else:
            return ConflictResolution(
                change=change,
                action="use_remote",
                message=f"Remote is newer ({remote_mtime} > {local_mtime})",
            )

    def _resolve_local_wins(self, change: FileChange) -> ConflictResolution:
        """Always prefer local version."""
        return ConflictResolution(
            change=change,
            action="use_local",
            message="Local wins strategy",
        )

    def _resolve_remote_wins(self, change: FileChange) -> ConflictResolution:
        """Always prefer remote version."""
        return ConflictResolution(
            change=change,
            action="use_remote",
            message="Remote wins strategy",
        )

    def _resolve_backup_both(self, change: FileChange) -> ConflictResolution:
        """Backup local version and use remote."""
        backup_path = self._create_backup(change.path)
        return ConflictResolution(
            change=change,
            action="use_remote",
            backup_path=backup_path,
            message=f"Backed up local to {backup_path}",
        )

    def _resolve_manual(self, change: FileChange) -> ConflictResolution:
        """Mark for manual resolution - don't change anything."""
        return ConflictResolution(
            change=change,
            action="skip",
            message="Marked for manual resolution",
        )

    def _create_backup(self, rel_path: str) -> Path:
        """Create a backup of a local file before overwriting."""
        source = self.vault_dir / rel_path
        if not source.exists():
            return None

        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{Path(rel_path).stem}_{timestamp}{Path(rel_path).suffix}"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(source, backup_path)
        logger.info("Created backup: %s -> %s", source, backup_path)
        return backup_path

    def resolve_all(self, conflicts: list[FileChange]) -> list[ConflictResolution]:
        """Resolve multiple conflicts."""
        return [self.resolve(c) for c in conflicts]


__all__ = ["ConflictStrategy", "ConflictResolution", "ConflictResolver"]
