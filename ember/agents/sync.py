"""Sync agent for vault synchronization status and initialization."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from ..configuration import ConfigurationBundle

logger = logging.getLogger("ember.agents.sync")


@dataclass
class SyncAgentResult:
    """Summary data returned after the sync agent runs."""

    status: Literal["ok", "pending", "disabled", "error"]
    detail: str
    node_id: str = ""
    mode: str = ""
    server_url: str = ""
    tracked_files: int = 0
    last_sync: Optional[str] = None
    pending_changes: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "node_id": self.node_id,
            "mode": self.mode,
            "server_url": self.server_url,
            "tracked_files": self.tracked_files,
            "last_sync": self.last_sync,
            "pending_changes": self.pending_changes,
            "errors": self.errors,
        }


def run_sync_agent(bundle: ConfigurationBundle) -> SyncAgentResult:
    """Initialize sync client and report vault sync status."""

    sync_config = bundle.merged.get("sync", {}) if bundle.merged else {}
    enabled = bool(sync_config.get("enabled", False))

    if not enabled:
        detail = "sync.agent disabled via configuration."
        logger.info(detail)
        return SyncAgentResult(status="disabled", detail=detail)

    # Import here to avoid circular imports
    from ..sync import SyncClient, SyncSettings

    try:
        settings = SyncSettings.from_config(bundle.merged)
        client = SyncClient(bundle.vault_dir, settings)

        # Get current status
        status_info = client.get_status()

        # Check for local changes since last sync
        pending_changes = 0
        delta = client.compute_local_delta()
        if delta is not None:
            pending_changes = delta.total_changes

        # Determine overall status
        if not settings.server_url and settings.mode != "manual":
            status = "pending"
            detail = "No sync server configured"
        elif pending_changes > 0:
            status = "pending"
            detail = f"{pending_changes} pending changes since last sync"
        else:
            status = "ok"
            detail = f"Tracking {status_info['tracked_files']} files"

        result = SyncAgentResult(
            status=status,
            detail=detail,
            node_id=settings.node_id or "(auto)",
            mode=settings.mode,
            server_url=settings.server_url or "(not configured)",
            tracked_files=status_info["tracked_files"],
            last_sync=status_info["last_sync"],
            pending_changes=pending_changes,
        )

        logger.info("sync.agent completed: %s", detail)
        return result

    except Exception as e:
        detail = f"Sync agent error: {e}"
        logger.exception(detail)
        return SyncAgentResult(
            status="error",
            detail=detail,
            errors=[str(e)],
        )


__all__ = ["run_sync_agent", "SyncAgentResult"]
