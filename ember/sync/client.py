"""Sync client for vault synchronization."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .conflict import ConflictResolver, ConflictResolution, ConflictStrategy
from .manifest import FileInfo, ManifestBuilder, VaultManifest, compute_file_hash
from .protocol import FileChange, SyncAction, SyncDelta, SyncRequest, SyncResponse, compute_delta

logger = logging.getLogger("ember.sync.client")


@dataclass
class SyncSettings:
    """Settings for sync operations."""

    enabled: bool = False
    node_id: str = ""
    mode: str = "manual"  # manual, auto
    server_url: str = ""
    conflict_strategy: str = "newest_wins"
    sync_dirs: tuple = ("config", "library", "notes", "reference")
    exclude_patterns: tuple = ("*.log", "*.tmp", "models/*", "state/*")
    manifest_path: str = "state/sync_manifest.json"

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "SyncSettings":
        raw = config.get("sync", {}) if config else {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            node_id=str(raw.get("node_id", "")),
            mode=str(raw.get("mode", "manual")),
            server_url=str(raw.get("server_url", "")),
            conflict_strategy=str(raw.get("conflict_strategy", "newest_wins")),
            sync_dirs=tuple(raw.get("sync_dirs", ["config", "library", "notes", "reference"])),
            exclude_patterns=tuple(raw.get("exclude_patterns", ["*.log", "*.tmp", "models/*", "state/*"])),
            manifest_path=str(raw.get("manifest_path", "state/sync_manifest.json")),
        )


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    uploaded: int = 0
    downloaded: int = 0
    conflicts_resolved: int = 0
    conflicts_pending: int = 0
    errors: List[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "uploaded": self.uploaded,
            "downloaded": self.downloaded,
            "conflicts_resolved": self.conflicts_resolved,
            "conflicts_pending": self.conflicts_pending,
            "errors": self.errors,
            "message": self.message,
        }


class SyncClient:
    """Client for vault synchronization with remote servers or peers."""

    def __init__(
        self,
        vault_dir: Path,
        settings: SyncSettings,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ):
        self.vault_dir = vault_dir
        self.settings = settings
        self.progress_callback = progress_callback

        # Initialize components
        self.builder = ManifestBuilder(
            vault_dir=vault_dir,
            node_id=settings.node_id,
            sync_dirs=list(settings.sync_dirs),
            exclude_patterns=list(settings.exclude_patterns),
        )

        strategy = ConflictStrategy(settings.conflict_strategy)
        self.resolver = ConflictResolver(vault_dir, strategy)

        self._manifest_path = vault_dir / settings.manifest_path

    def build_manifest(self) -> VaultManifest:
        """Build a fresh manifest of local vault contents."""
        return self.builder.build()

    def load_manifest(self) -> Optional[VaultManifest]:
        """Load the last saved manifest."""
        return VaultManifest.load(self._manifest_path)

    def save_manifest(self, manifest: VaultManifest) -> None:
        """Save the current manifest."""
        manifest.save(self._manifest_path)

    def compute_local_delta(self) -> Optional[SyncDelta]:
        """Compute changes since last sync by comparing current state to saved manifest."""
        old_manifest = self.load_manifest()
        if old_manifest is None:
            logger.info("No previous manifest found - all files are new")
            return None

        current_manifest = self.build_manifest()
        return compute_delta(current_manifest, old_manifest)

    def sync_with_server(self, server_url: Optional[str] = None) -> SyncResult:
        """Perform a full sync with the remote server."""
        url = server_url or self.settings.server_url
        if not url:
            return SyncResult(
                success=False,
                message="No server URL configured",
            )

        result = SyncResult(success=True)

        try:
            # Build local manifest
            local_manifest = self.build_manifest()
            self._report_progress("Building manifest", 1, 5)

            # Send sync request to server
            request = SyncRequest(
                node_id=self.settings.node_id,
                manifest=local_manifest,
                request_type="full",
            )

            response = self._send_request(url, request)
            self._report_progress("Received response", 2, 5)

            if response.status != "ok":
                return SyncResult(
                    success=False,
                    message=f"Server error: {response.message}",
                )

            if response.delta is None:
                result.message = "Already in sync"
                return result

            delta = response.delta

            # Handle uploads
            if delta.to_upload:
                uploaded = self._upload_files(url, delta.to_upload)
                result.uploaded = uploaded
            self._report_progress("Uploaded files", 3, 5)

            # Handle downloads
            if delta.to_download:
                downloaded = self._download_files(response.files)
                result.downloaded = downloaded
            self._report_progress("Downloaded files", 4, 5)

            # Handle conflicts
            if delta.conflicts:
                resolutions = self.resolver.resolve_all(delta.conflicts)
                for res in resolutions:
                    if res.action == "skip":
                        result.conflicts_pending += 1
                    else:
                        result.conflicts_resolved += 1
                        self._apply_resolution(res, response.files)

            # Save updated manifest
            self.save_manifest(local_manifest)
            self._report_progress("Sync complete", 5, 5)

            result.message = delta.summary()

        except HTTPError as e:
            result.success = False
            result.message = f"HTTP error: {e.code} {e.reason}"
            result.errors.append(str(e))
        except URLError as e:
            result.success = False
            result.message = f"Connection error: {e.reason}"
            result.errors.append(str(e))
        except Exception as e:
            result.success = False
            result.message = f"Sync failed: {e}"
            result.errors.append(str(e))
            logger.exception("Sync failed")

        return result

    def _send_request(self, url: str, request: SyncRequest) -> SyncResponse:
        """Send a sync request to the server."""
        endpoint = f"{url.rstrip('/')}/api/v1/sync"
        data = json.dumps(request.to_dict()).encode("utf-8")

        req = Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(req, timeout=30) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
            return SyncResponse.from_dict(response_data)

    def _upload_files(self, url: str, changes: List[FileChange]) -> int:
        """Upload files to the server."""
        uploaded = 0
        endpoint = f"{url.rstrip('/')}/api/v1/sync/upload"

        for change in changes:
            try:
                file_path = self.vault_dir / change.path
                if not file_path.exists():
                    logger.warning("File not found for upload: %s", change.path)
                    continue

                content = file_path.read_bytes()
                change.content = content

                data = json.dumps(change.to_dict()).encode("utf-8")
                req = Request(
                    endpoint,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with urlopen(req, timeout=60) as resp:
                    if resp.status == 200:
                        uploaded += 1
                        logger.debug("Uploaded: %s", change.path)

            except Exception as e:
                logger.error("Failed to upload %s: %s", change.path, e)

        return uploaded

    def _download_files(self, files: List[FileChange]) -> int:
        """Download and save files from the response."""
        downloaded = 0

        for change in files:
            if change.content is None:
                continue

            try:
                file_path = self.vault_dir / change.path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(change.content)

                # Restore file mode if available
                if change.remote_info and change.remote_info.mode:
                    file_path.chmod(change.remote_info.mode)

                downloaded += 1
                logger.debug("Downloaded: %s", change.path)

            except Exception as e:
                logger.error("Failed to download %s: %s", change.path, e)

        return downloaded

    def _apply_resolution(
        self,
        resolution: ConflictResolution,
        available_files: List[FileChange],
    ) -> None:
        """Apply a conflict resolution."""
        if resolution.action == "use_remote":
            # Find the file in available downloads
            for file_change in available_files:
                if file_change.path == resolution.change.path and file_change.content:
                    file_path = self.vault_dir / file_change.path
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_bytes(file_change.content)
                    logger.info("Applied remote version: %s", file_change.path)
                    break

        elif resolution.action == "use_local":
            # Local version is already in place, nothing to do
            logger.info("Kept local version: %s", resolution.change.path)

    def _report_progress(self, message: str, current: int, total: int) -> None:
        """Report progress if callback is configured."""
        if self.progress_callback:
            self.progress_callback(message, current, total)
        logger.debug("Sync progress: %s (%d/%d)", message, current, total)

    def get_status(self) -> Dict[str, Any]:
        """Get current sync status."""
        manifest = self.load_manifest()
        return {
            "enabled": self.settings.enabled,
            "mode": self.settings.mode,
            "server_url": self.settings.server_url or "(not configured)",
            "node_id": self.settings.node_id or "(not set)",
            "last_sync": manifest.created_at if manifest else None,
            "tracked_files": len(manifest.files) if manifest else 0,
            "sync_dirs": list(self.settings.sync_dirs),
        }


__all__ = ["SyncClient", "SyncSettings", "SyncResult"]
