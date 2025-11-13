"""Agent implementations for the Ember runtime."""

from .provision import run_provision_agent
from .registry import AgentDefinition, AgentRegistry

REGISTRY = AgentRegistry()
REGISTRY.register(
    AgentDefinition(
        name="provision.agent",
        description="Ensure the vault layout exists and record provisioning state.",
        handler=run_provision_agent,
        triggers=("bootstrap",),
    )
)

__all__ = [
    "REGISTRY",
    "AgentDefinition",
    "AgentRegistry",
]
