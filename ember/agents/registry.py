"""Agent registry and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from ..configuration import ConfigurationBundle, Diagnostic

logger = logging.getLogger("ember.agents.registry")

AgentHandler = Callable[[ConfigurationBundle], Any]


@dataclass
class AgentDefinition:
    """Metadata describing an agent implementation."""

    name: str
    description: str
    handler: AgentHandler
    triggers: Sequence[str] = field(default_factory=lambda: ("bootstrap",))
    default_enabled: bool = True
    requires_ready: bool = True


class AgentRegistry:
    """Registry that tracks available agents and runs them by trigger."""

    def __init__(self) -> None:
        self._registry: Dict[str, AgentDefinition] = {}

    def register(self, definition: AgentDefinition) -> None:
        key = definition.name.lower().strip()
        if not key:
            raise ValueError("Agent name cannot be empty.")
        self._registry[key] = definition
        logger.debug("Registered agent '%s'.", key)

    def definitions(self) -> Sequence[AgentDefinition]:
        return list(self._registry.values())

    def definition(self, name: str) -> Optional[AgentDefinition]:
        return self._registry.get(name.lower())

    def enabled(self, bundle: ConfigurationBundle) -> Dict[str, bool]:
        config_agents = bundle.merged.get("agents", {}) if bundle.merged else {}
        enabled_raw = config_agents.get("enabled")
        disabled_raw = config_agents.get("disabled")

        def _normalize(raw) -> List[str]:
            if isinstance(raw, str):
                return [raw]
            if isinstance(raw, Sequence):
                return [str(item).lower().strip() for item in raw if str(item).strip()]
            return []

        enabled = set(_normalize(enabled_raw))
        disabled = set(_normalize(disabled_raw))

        states: Dict[str, bool] = {}
        for definition in self._registry.values():
            name = definition.name.lower()
            if enabled:
                states[name] = name in enabled
                continue
            if name in disabled:
                states[name] = False
                continue
            states[name] = definition.default_enabled
        return states

    def run(
        self,
        bundle: ConfigurationBundle,
        *,
        trigger: str = "bootstrap",
    ) -> Dict[str, Any]:
        """Run all agents matching the trigger and enabled status."""

        results: Dict[str, Any] = {}
        enabled_state = self.enabled(bundle)
        for definition in self._registry.values():
            name = definition.name.lower()
            if trigger not in definition.triggers:
                continue
            if not enabled_state.get(name, False):
                logger.info("Skipping agent '%s' (disabled).", definition.name)
                continue
            if definition.requires_ready and bundle.status != "ready":
                logger.info(
                    "Skipping agent '%s' because configuration status is '%s'.",
                    definition.name,
                    bundle.status,
                )
                continue
            try:
                result = definition.handler(bundle)
            except Exception as exc:  # pragma: no cover - logged and surfaced
                logger.exception("Agent '%s' failed: %s", definition.name, exc)
                bundle.diagnostics.append(
                    Diagnostic(
                        level="error",
                        message=f"Agent '{definition.name}' failed: {exc}",
                    )
                )
                results[definition.name] = {
                    "status": "error",
                    "detail": str(exc),
                }
                continue
            results[definition.name] = _normalize_agent_result(result)
        return results


def _normalize_agent_result(result: Any) -> Any:
    """Normalize agent handler output so `/status` can render it."""

    if result is None:
        return {"status": "ok"}
    if hasattr(result, "to_dict"):
        try:
            return result.to_dict()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            logger.warning("Agent result to_dict() failed; falling back to string.")
    if isinstance(result, dict):
        return result
    return {"status": "ok", "detail": str(result)}


__all__ = ["AgentDefinition", "AgentRegistry"]
