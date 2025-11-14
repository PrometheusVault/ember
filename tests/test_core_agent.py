from ember.agents.core import run_core_agent
from ember.configuration import ConfigurationBundle


def test_core_agent_summary_handles_lists(tmp_path):
    bundle = ConfigurationBundle(
        vault_dir=tmp_path,
        status="ready",
        merged={
            "agents": {
                "enabled": [" network.agent ", "PROVISION.AGENT"],
                "disabled": "test.agent",
            }
        },
    )

    summary = run_core_agent(bundle).to_dict()

    assert summary["status"] == "ok"
    assert summary["configuration"] == "ready"
    assert summary["allow_list"] == ["network.agent", "provision.agent"]
    assert summary["deny_list"] == ["test.agent"]
    assert summary["vault"] == str(tmp_path)


def test_core_agent_summary_blocks_when_not_ready(tmp_path):
    bundle = ConfigurationBundle(vault_dir=tmp_path, status="missing")
    summary = run_core_agent(bundle).to_dict()
    assert summary["status"] == "blocked"
    assert summary["allow_list"] == []
