"""Network agent that reports interface and connectivity state."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import socket
import time
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from ..configuration import ConfigurationBundle, Diagnostic

try:  # pragma: no cover - exercised via tests using monkeypatch
    import psutil  # type: ignore
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore

logger = logging.getLogger("ember.network")

DEFAULT_CONNECTIVITY_TIMEOUT = 1.0
DEFAULT_DNS_PATHS: Sequence[str] = ("/etc/resolv.conf",)


@dataclass
class NetworkSettings:
    """Runtime configuration for the network agent."""

    enabled: bool
    preferred_interfaces: Sequence[str]
    include_loopback: bool
    connectivity_checks: Sequence[str]
    connectivity_timeout: float
    dns_paths: Sequence[str]

    @classmethod
    def from_bundle(cls, bundle: ConfigurationBundle) -> "NetworkSettings":
        raw = bundle.merged.get("network", {}) if bundle.merged else {}

        def _string_list(key: str) -> List[str]:
            values = raw.get(key, [])
            if isinstance(values, str):
                values = [values]
            normalized: List[str] = []
            if isinstance(values, Sequence):
                for item in values:
                    text = str(item).strip()
                    if text:
                        normalized.append(text)
            return normalized

        timeout_raw = raw.get("connectivity_timeout", DEFAULT_CONNECTIVITY_TIMEOUT)
        try:
            timeout = float(timeout_raw)
            if timeout <= 0:
                timeout = DEFAULT_CONNECTIVITY_TIMEOUT
        except (TypeError, ValueError):
            timeout = DEFAULT_CONNECTIVITY_TIMEOUT

        dns_paths = _string_list("dns_paths") or list(DEFAULT_DNS_PATHS)

        return cls(
            enabled=bool(raw.get("enabled", True)),
            preferred_interfaces=tuple(_string_list("preferred_interfaces")),
            include_loopback=bool(raw.get("include_loopback", False)),
            connectivity_checks=tuple(_string_list("connectivity_checks")),
            connectivity_timeout=timeout,
            dns_paths=tuple(dns_paths),
        )


def run_network_agent(bundle: ConfigurationBundle) -> Dict[str, Any]:
    """Collect interface details and optional connectivity checks."""

    settings = NetworkSettings.from_bundle(bundle)

    if not settings.enabled:
        detail = "network.agent disabled via configuration."
        logger.info(detail)
        return {
            "status": "skipped",
            "detail": detail,
            "interfaces": [],
            "dns": [],
            "connectivity": [],
        }

    if psutil is None:
        detail = "psutil is not installed; network inspection unavailable."
        bundle.diagnostics.append(
            Diagnostic(level="error", message=detail, source=Path("psutil"))
        )
        logger.error(detail)
        return {
            "status": "error",
            "detail": detail,
            "interfaces": [],
            "dns": [],
            "connectivity": [],
        }

    interfaces = _collect_interfaces(settings)
    dns_servers = _load_dns_servers(settings.dns_paths)
    connectivity = _run_connectivity_checks(
        settings.connectivity_checks,
        timeout=settings.connectivity_timeout,
    )

    any_up = any(info.get("is_up") for info in interfaces)
    primary = _select_primary_interface(interfaces, settings.preferred_interfaces)

    detail_parts = []
    if interfaces:
        detail_parts.append(
            f"{sum(1 for info in interfaces if info.get('is_up'))} up / {len(interfaces)} total interfaces"
        )
    else:
        detail_parts.append("no interfaces detected")
    if primary:
        detail_parts.append(f"primary={primary}")
    if connectivity:
        success = sum(1 for entry in connectivity if entry.get("reachable"))
        detail_parts.append(f"connectivity {success}/{len(connectivity)} targets")
    status: Literal["ok", "degraded"] = "ok" if any_up else "degraded"
    detail = "; ".join(detail_parts)

    result = {
        "status": status,
        "detail": detail,
        "primary_interface": primary,
        "interfaces": interfaces,
        "dns": dns_servers,
        "connectivity": connectivity,
    }

    logger.info("network.agent completed: %s", detail)
    return result


def _collect_interfaces(settings: NetworkSettings) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    addrs = psutil.net_if_addrs()  # type: ignore[attr-defined]
    stats = psutil.net_if_stats()  # type: ignore[attr-defined]
    af_link = getattr(psutil, "AF_LINK", None)

    for name, entries in addrs.items():
        if not settings.include_loopback and _is_loopback(name, entries):
            continue

        entry_stats = stats.get(name)
        interface: Dict[str, Any] = {
            "name": name,
            "is_up": bool(getattr(entry_stats, "isup", False)),
            "mtu": getattr(entry_stats, "mtu", None),
            "speed_mbps": getattr(entry_stats, "speed", None),
            "addresses": [],
            "mac": None,
        }

        for addr in entries:
            family = getattr(addr, "family", None)
            address = getattr(addr, "address", "")
            netmask = getattr(addr, "netmask", None)
            broadcast = getattr(addr, "broadcast", None)
            if family == socket.AF_INET:
                interface["addresses"].append(
                    {
                        "family": "ipv4",
                        "address": address,
                        "netmask": netmask,
                        "broadcast": broadcast,
                    }
                )
            elif family == socket.AF_INET6:
                interface["addresses"].append(
                    {
                        "family": "ipv6",
                        "address": address,
                        "netmask": netmask,
                        "broadcast": broadcast,
                    }
                )
            elif af_link is not None and family == af_link:
                interface["mac"] = address

        # drop interfaces that only had MAC data unless explicitly loopback included
        if not interface["addresses"] and interface["mac"] is None:
            continue
        reports.append(interface)

    # Stable ordering: preferred interfaces first, then alphabetical
    def _sort_key(item: Dict[str, Any]) -> Tuple[int, str]:
        name = item.get("name", "")
        try:
            preferred_index = settings.preferred_interfaces.index(name)
        except ValueError:
            preferred_index = len(settings.preferred_interfaces)
        return preferred_index, name

    reports.sort(key=_sort_key)
    return reports


def _is_loopback(name: str, entries: Sequence[Any]) -> bool:
    lowered = name.lower()
    if lowered.startswith("lo"):
        return True
    for addr in entries:
        address = getattr(addr, "address", "")
        if isinstance(address, str) and (
            address.startswith("127.") or address in {"::1", "0:0:0:0:0:0:0:1"}
        ):
            return True
    return False


def _load_dns_servers(paths: Sequence[str]) -> List[str]:
    servers: List[str] = []
    for raw in paths:
        path = Path(raw)
        if not path.exists() or not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.lower().startswith("nameserver"):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
        except OSError as exc:  # pragma: no cover - filesystem issues
            logger.debug("Unable to read DNS config %s: %s", path, exc)
    return servers


def _run_connectivity_checks(
    targets: Sequence[str],
    *,
    timeout: float,
) -> List[Dict[str, Any]]:
    if not targets:
        return []

    results: List[Dict[str, Any]] = []
    for target in targets:
        host, port = _parse_target(target)
        formatted = f"{host}:{port}"
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                latency = (time.perf_counter() - start) * 1000
                results.append(
                    {
                        "target": formatted,
                        "reachable": True,
                        "latency_ms": round(latency, 2),
                    }
                )
        except OSError as exc:
            results.append(
                {
                    "target": formatted,
                    "reachable": False,
                    "detail": str(exc),
                }
            )
    return results


def _parse_target(target: str) -> Tuple[str, int]:
    default_port = 443
    stripped = target.strip()
    if not stripped:
        return ("localhost", default_port)
    if stripped.count(":") == 1 and stripped.split(":", 1)[1].isdigit():
        host, raw_port = stripped.split(":", 1)
        try:
            port = int(raw_port)
        except ValueError:
            port = default_port
        return (host or "localhost", port)
    return (stripped, default_port)


def _select_primary_interface(
    interfaces: Sequence[Dict[str, Any]],
    preferred: Sequence[str],
) -> Optional[str]:
    preferred_set = [name for name in preferred if name]
    for name in preferred_set:
        for interface in interfaces:
            if interface.get("name") == name and interface.get("is_up"):
                return name
    for interface in interfaces:
        if interface.get("is_up"):
            return str(interface.get("name"))
    return interfaces[0]["name"] if interfaces else None


__all__ = ["run_network_agent", "NetworkSettings"]
