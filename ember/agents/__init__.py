"""Agent implementations for the Ember runtime."""

from .core import run_core_agent
from .health import run_health_agent
from .network import run_network_agent
from .plugin_loader import run_plugin_agent
from .provision import run_provision_agent
from .registry import AgentDefinition, AgentRegistry
from .test_runner import run_test_agent
from .toolchain import run_toolchain_agent
from .update_agent import run_update_agent

REGISTRY = AgentRegistry()
REGISTRY.register(
    AgentDefinition(
        name="core.agent",
        description="Coordinate bootstrap sequencing and record agent policy.",
        handler=run_core_agent,
        triggers=("bootstrap",),
        requires_ready=False,
    )
)
REGISTRY.register(
    AgentDefinition(
        name="network.agent",
        description="Inspect network interfaces and optionally run connectivity checks.",
        handler=run_network_agent,
        triggers=("bootstrap",),
        requires_ready=False,
    )
)
REGISTRY.register(
    AgentDefinition(
        name="provision.agent",
        description="Ensure the vault layout exists and record provisioning state.",
        handler=run_provision_agent,
        triggers=("bootstrap",),
    )
)
REGISTRY.register(
    AgentDefinition(
        name="toolchain.agent",
        description="Verify developer tooling (docker, make, python deps) is ready.",
        handler=run_toolchain_agent,
        triggers=("bootstrap",),
    )
)
REGISTRY.register(
    AgentDefinition(
        name="test.agent",
        description="Execute the configured test suite and capture its result.",
        handler=run_test_agent,
        triggers=("bootstrap",),
        default_enabled=False,
    )
)
REGISTRY.register(
    AgentDefinition(
        name="plugin.agent",
        description="Discover plugins from the repo, vault, and system paths.",
        handler=run_plugin_agent,
        triggers=("bootstrap",),
        requires_ready=False,
    )
)
REGISTRY.register(
    AgentDefinition(
        name="update.agent",
        description="Summarize git status/branch readiness for updates.",
        handler=run_update_agent,
        triggers=("bootstrap",),
        default_enabled=False,
    )
)
REGISTRY.register(
    AgentDefinition(
        name="health.agent",
        description="Monitor system health metrics (CPU, memory, disk, temperature).",
        handler=run_health_agent,
        triggers=("bootstrap",),
        requires_ready=False,
    )
)

__all__ = [
    "REGISTRY",
    "AgentDefinition",
    "AgentRegistry",
]
