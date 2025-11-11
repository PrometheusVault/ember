"""Provision agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence

from ..configuration import ConfigurationBundle, Diagnostic

logger = logging.getLogger("ember.provision")

DEFAULT_REQUIRED_PATHS: Sequence[str] = (
    "config",
    "logs",
    "logs/agents",
    "models",
    "plugins",
    "state",
)
DEFAULT_SKIP_ENV = "EMBER_SKIP_PROVISION"
DEFAULT_STATE_FILE = "state/provision.json"


@dataclass
class ProvisionSettings:
    """Runtime settings that control the provision agent."""

    enabled: bool
    skip_env: str
    required_paths: Sequence[str]
    state_file: str

    @classmethod
    def from_bundle(cls, bundle: ConfigurationBundle) -> "ProvisionSettings":
        raw_settings = bundle.merged.get("provision", {}) if bundle.merged else {}
        enabled = bool(raw_settings.get("enabled", True))
        skip_env = str(raw_settings.get("skip_env", DEFAULT_SKIP_ENV))
        raw_paths = raw_settings.get("required_paths", DEFAULT_REQUIRED_PATHS)
        if not raw_paths:
            raw_paths = DEFAULT_REQUIRED_PATHS

        normalized_paths: List[str] = []
        for path in raw_paths:
            cleaned = str(path).strip()
            if cleaned:
                normalized_paths.append(cleaned)

        if not normalized_paths:
            normalized_paths = list(DEFAULT_REQUIRED_PATHS)

        state_file = str(raw_settings.get("state_file", DEFAULT_STATE_FILE)).strip()
        if not state_file:
            state_file = DEFAULT_STATE_FILE

        return cls(
            enabled=enabled,
            skip_env=skip_env,
            required_paths=tuple(normalized_paths),
            state_file=state_file,
        )


@dataclass
class ProvisionResult:
    """Summary data returned after the provision agent runs."""

    status: Literal["completed", "partial", "skipped"]
    detail: str
    created_paths: List[Path] = field(default_factory=list)
    verified_paths: List[Path] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    state_path: Optional[Path] = None
    last_run: Optional[datetime] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "detail": self.detail,
            "created": [str(path) for path in self.created_paths],
            "verified": [str(path) for path in self.verified_paths],
            "issues": list(self.issues),
            "state_file": str(self.state_path) if self.state_path else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }


def run_provision_agent(bundle: ConfigurationBundle) -> ProvisionResult:
    """
    Ensure the vault directory has the expected layout and record a provisioning state file.
    """

    settings = ProvisionSettings.from_bundle(bundle)
    state_path = _resolve_path(bundle.vault_dir, settings.state_file)

    if not settings.enabled:
        detail = "provision.agent disabled via configuration."
        logger.info("provision.agent skipped: %s", detail)
        return ProvisionResult(status="skipped", detail=detail, state_path=state_path)

    if bundle.status != "ready":
        detail = f"configuration status '{bundle.status}' is not ready."
        logger.warning("provision.agent skipped: %s", detail)
        return ProvisionResult(status="skipped", detail=detail, state_path=state_path)

    if os.environ.get(settings.skip_env):
        detail = f"environment variable {settings.skip_env} is set."
        logger.info("provision.agent skipped: %s", detail)
        return ProvisionResult(status="skipped", detail=detail, state_path=state_path)

    created: List[Path] = []
    verified: List[Path] = []
    issues: List[str] = []

    for relative_path in settings.required_paths:
        target = _resolve_path(bundle.vault_dir, relative_path)
        if target.exists():
            if target.is_dir():
                verified.append(target)
            else:
                message = f"Expected '{target}' to be a directory."
                issues.append(message)
                bundle.diagnostics.append(
                    Diagnostic(level="error", message=message, source=target)
                )
            continue

        try:
            target.mkdir(parents=True, exist_ok=True)
            created.append(target)
        except OSError as exc:  # pragma: no cover - exercised via diagnostics
            message = f"Unable to create '{target}': {exc}"
            issues.append(message)
            bundle.diagnostics.append(
                Diagnostic(level="warning", message=message, source=target)
            )

    last_run = datetime.now(timezone.utc)
    detail_parts = []
    if created:
        detail_parts.append(f"created {len(created)} path(s)")
    if verified:
        detail_parts.append(f"verified {len(verified)} existing path(s)")
    if not detail_parts:
        detail_parts.append("no paths required provisioning")

    result = ProvisionResult(
        status="completed",
        detail="; ".join(detail_parts),
        created_paths=created,
        verified_paths=verified,
        issues=issues.copy(),
        state_path=state_path,
        last_run=last_run,
    )

    state_error = _write_state_file(
        state_path,
        last_run,
        created,
        verified,
        issues,
        bundle,
    )
    if state_error:
        issues.append(state_error)
        result.issues.append(state_error)

    if issues:
        result.status = "partial"
        result.detail = f"{result.detail}; {len(issues)} issue(s) recorded"
        logger.warning("provision.agent partial: %s", result.detail)
    else:
        logger.info("provision.agent completed: %s", result.detail)

    return result


def _resolve_path(vault_dir: Path, raw_path: str) -> Path:
    """Resolve raw config paths relative to the vault unless already absolute."""

    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return vault_dir / candidate


def _write_state_file(
    state_path: Path,
    timestamp: datetime,
    created: Sequence[Path],
    verified: Sequence[Path],
    issues: Sequence[str],
    bundle: ConfigurationBundle,
) -> Optional[str]:
    """Persist provisioning metadata for future sessions."""

    payload = {
        "status": "partial" if issues else "completed",
        "last_run": timestamp.isoformat(),
        "created": [str(path) for path in created],
        "verified": [str(path) for path in verified],
        "issues": list(issues),
    }

    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:  # pragma: no cover - relies on filesystem perms
        message = f"Unable to write provisioning state to '{state_path}': {exc}"
        bundle.diagnostics.append(
            Diagnostic(level="warning", message=message, source=state_path)
        )
        logger.warning(message)
        return message
    return None
