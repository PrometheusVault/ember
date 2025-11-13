"""Unit tests for the network agent."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import socket

from ember.agents import network
from ember.configuration import ConfigurationBundle


def _bundle(tmp_path: Path, merged: dict | None = None) -> ConfigurationBundle:
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(exist_ok=True)
    return ConfigurationBundle(
        vault_dir=vault_dir,
        status="ready",
        merged=merged or {},
        diagnostics=[],
    )


def test_network_agent_reports_interfaces(tmp_path: Path, monkeypatch):
    resolv_conf = tmp_path / "resolv.conf"
    resolv_conf.write_text("nameserver 1.1.1.1\n", encoding="utf-8")

    def _addr(family, address, netmask=None, broadcast=None):
        return SimpleNamespace(
            family=family,
            address=address,
            netmask=netmask,
            broadcast=broadcast,
        )

    class _Stats:
        def __init__(self, isup: bool) -> None:
            self.isup = isup
            self.mtu = 1500
            self.speed = 1000

    fake_psutil = SimpleNamespace(
        AF_LINK=object(),
        net_if_addrs=lambda: {
            "eth0": [
                _addr(socket.AF_INET, "192.168.0.10", "255.255.255.0", "192.168.0.255"),
                _addr(socket.AF_INET6, "fe80::1"),
            ],
            "lo": [_addr(socket.AF_INET, "127.0.0.1", "255.0.0.0")],
        },
        net_if_stats=lambda: {"eth0": _Stats(True), "lo": _Stats(True)},
    )

    monkeypatch.setattr(network, "psutil", fake_psutil)
    monkeypatch.setattr(
        network,
        "_run_connectivity_checks",
        lambda targets, timeout: [{"target": "1.1.1.1:53", "reachable": True}],
    )

    bundle = _bundle(
        tmp_path,
        merged={
            "network": {
                "preferred_interfaces": ["eth0"],
                "dns_paths": [str(resolv_conf)],
                "connectivity_checks": ["1.1.1.1:53"],
            }
        },
    )

    result = network.run_network_agent(bundle)

    assert result["status"] == "ok"
    assert result["primary_interface"] == "eth0"
    assert result["dns"] == ["1.1.1.1"]
    assert result["interfaces"][0]["name"] == "eth0"
    assert result["interfaces"][0]["addresses"][0]["address"] == "192.168.0.10"
    assert result["connectivity"][0]["reachable"] is True


def test_network_agent_skips_when_disabled(tmp_path: Path):
    bundle = _bundle(tmp_path, merged={"network": {"enabled": False}})
    result = network.run_network_agent(bundle)
    assert result["status"] == "skipped"
    assert result["interfaces"] == []


def test_network_agent_errors_when_psutil_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(network, "psutil", None)
    bundle = _bundle(tmp_path)

    result = network.run_network_agent(bundle)

    assert result["status"] == "error"
    assert any("psutil" in diag.message for diag in bundle.diagnostics)


def test_run_connectivity_checks_handles_success_and_failure(monkeypatch):
    calls: list[tuple[str, int]] = []

    class _Conn:
        def __enter__(self):  # pragma: no cover - structure only
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def close(self):  # pragma: no cover - compatibility
            return None

    def fake_create_connection(addr, timeout=None):
        host, port = addr
        calls.append((host, port))
        if host == "offline":
            raise OSError("unreachable")
        return _Conn()

    monkeypatch.setattr(network.socket, "create_connection", fake_create_connection)

    results = network._run_connectivity_checks(["online:80", "offline:80"], timeout=0.1)

    assert calls == [("online", 80), ("offline", 80)]
    assert results[0]["reachable"] is True
    assert results[1]["reachable"] is False
