from pathlib import Path

from ember.configuration import ConfigurationBundle
from ember.agents.registry import AgentDefinition, AgentRegistry


def _bundle(tmp_path: Path, status: str = "ready") -> ConfigurationBundle:
    return ConfigurationBundle(vault_dir=tmp_path, status=status)


def test_registry_runs_enabled_agent(tmp_path: Path):
    bundle = _bundle(tmp_path)
    registry = AgentRegistry()
    hits = {}

    def handler(cfg):
        hits["ran"] = True
        return {"status": "completed"}

    registry.register(
        AgentDefinition(
            name="demo.agent",
            description="Demo agent",
            handler=handler,
        )
    )

    results = registry.run(bundle)

    assert hits.get("ran") is True
    assert results["demo.agent"]["status"] == "completed"


def test_registry_respects_enabled_list(tmp_path: Path):
    bundle = _bundle(tmp_path)
    bundle.merged["agents"] = {"enabled": ["other.agent"]}
    registry = AgentRegistry()
    hits = {}

    registry.register(
        AgentDefinition(
            name="demo.agent",
            description="Demo agent",
            handler=lambda cfg: hits.setdefault("ran", True),
        )
    )

    results = registry.run(bundle)

    assert "ran" not in hits
    assert "demo.agent" not in results


def test_registry_disables_via_status(tmp_path: Path):
    bundle = _bundle(tmp_path, status="invalid")
    registry = AgentRegistry()
    hits = {}

    registry.register(
        AgentDefinition(
            name="demo.agent",
            description="Demo agent",
            handler=lambda cfg: hits.setdefault("ran", True),
            requires_ready=True,
        )
    )

    results = registry.run(bundle)

    assert "ran" not in hits
    assert "demo.agent" not in results


def test_registry_records_errors(tmp_path: Path):
    bundle = _bundle(tmp_path)
    registry = AgentRegistry()

    def handler(cfg):
        raise RuntimeError("boom")

    registry.register(
        AgentDefinition(
            name="flaky.agent",
            description="Boom",
            handler=handler,
        )
    )

    results = registry.run(bundle)

    assert results["flaky.agent"]["status"] == "error"
    assert bundle.diagnostics, "Expected diagnostic entry on failure"
