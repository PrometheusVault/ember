"""Core agent shim that records bootstrap intent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import List, Sequence

from ..configuration import ConfigurationBundle

logger = logging.getLogger("ember.core")


def _normalize(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates: Sequence[object] = [value]
    elif isinstance(value, Sequence):
        candidates = value
    else:
        return []
    normalized: List[str] = []
    for item in candidates:
        text = str(item).strip()
        if text:
            normalized.append(text.lower())
    return normalized


@dataclass
class CoreAgentSummary:
    status: str
    detail: str
    configuration: str
    vault: str
    allow_list: List[str]
    deny_list: List[str]
    last_run: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "detail": self.detail,
            "configuration": self.configuration,
            "vault": self.vault,
            "allow_list": list(self.allow_list),
            "deny_list": list(self.deny_list),
            "last_run": self.last_run,
        }


def run_core_agent(bundle: ConfigurationBundle) -> CoreAgentSummary:
    """Summarize the configuration/agent policy before other agents run."""

    agents_block = bundle.merged.get("agents", {}) if bundle.merged else {}
    allowed = _normalize(agents_block.get("enabled"))
    denied = _normalize(agents_block.get("disabled"))

    policy = "allowlist" if allowed else "defaults"
    detail = f"configuration={bundle.status}; policy={policy}"
    if denied:
        detail += f"; denying {len(denied)} agent(s)"

    status = "ok" if bundle.status == "ready" else "blocked"
    timestamp = datetime.now(timezone.utc).isoformat()

    summary = CoreAgentSummary(
        status=status,
        detail=detail,
        configuration=bundle.status,
        vault=str(bundle.vault_dir),
        allow_list=allowed,
        deny_list=denied,
        last_run=timestamp,
    )

    logger.info("core.agent prepared bootstrap plan (%s).", summary.detail)
    return summary


__all__ = ["run_core_agent", "CoreAgentSummary"]
