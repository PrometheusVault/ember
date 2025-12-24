"""Health monitoring agent that reports system metrics and alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

from ..configuration import ConfigurationBundle, Diagnostic

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

logger = logging.getLogger("ember.agents.health")

DEFAULT_CHECK_PATHS: Sequence[str] = ("/",)


@dataclass
class HealthSettings:
    """Runtime configuration for the health agent."""

    enabled: bool = True
    cpu_temp_warning: float = 70.0
    cpu_temp_critical: float = 80.0
    memory_warning_percent: float = 80.0
    disk_warning_percent: float = 85.0
    check_paths: tuple = ("/",)

    @classmethod
    def from_bundle(cls, bundle: ConfigurationBundle) -> "HealthSettings":
        raw = bundle.merged.get("health", {}) if bundle.merged else {}

        def _float_val(key: str, default: float) -> float:
            val = raw.get(key, default)
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        check_paths = raw.get("check_paths", list(DEFAULT_CHECK_PATHS))
        if isinstance(check_paths, str):
            check_paths = [check_paths]

        return cls(
            enabled=bool(raw.get("enabled", True)),
            cpu_temp_warning=_float_val("cpu_temp_warning", 70.0),
            cpu_temp_critical=_float_val("cpu_temp_critical", 80.0),
            memory_warning_percent=_float_val("memory_warning_percent", 80.0),
            disk_warning_percent=_float_val("disk_warning_percent", 85.0),
            check_paths=tuple(str(p) for p in check_paths if p),
        )


@dataclass
class HealthResult:
    """Summary data returned after the health agent runs."""

    status: Literal["ok", "warning", "critical", "skipped", "error"]
    detail: str
    cpu_temp: Optional[float] = None
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_available_mb: float = 0.0
    disk_usage: Dict[str, float] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "cpu_temp": self.cpu_temp,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_available_mb": self.memory_available_mb,
            "disk_usage": self.disk_usage,
            "alerts": self.alerts,
        }


def run_health_agent(bundle: ConfigurationBundle) -> HealthResult:
    """Check system health metrics and report alerts."""

    settings = HealthSettings.from_bundle(bundle)

    if not settings.enabled:
        detail = "health.agent disabled via configuration."
        logger.info(detail)
        return HealthResult(status="skipped", detail=detail)

    if psutil is None:
        detail = "psutil is not installed; health monitoring unavailable."
        bundle.diagnostics.append(
            Diagnostic(level="error", message=detail, source=Path("psutil"))
        )
        logger.error(detail)
        return HealthResult(status="error", detail=detail)

    alerts: List[str] = []
    status: Literal["ok", "warning", "critical"] = "ok"

    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.5)

    # CPU temperature (if available)
    cpu_temp: Optional[float] = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Try common sensor names
            for sensor_name in ("coretemp", "cpu_thermal", "cpu-thermal", "acpitz"):
                if sensor_name in temps and temps[sensor_name]:
                    cpu_temp = temps[sensor_name][0].current
                    break
            # Fall back to first available sensor
            if cpu_temp is None:
                for entries in temps.values():
                    if entries:
                        cpu_temp = entries[0].current
                        break

        if cpu_temp is not None:
            if cpu_temp >= settings.cpu_temp_critical:
                alerts.append(f"CPU temperature critical: {cpu_temp:.1f}°C")
                status = "critical"
            elif cpu_temp >= settings.cpu_temp_warning:
                alerts.append(f"CPU temperature warning: {cpu_temp:.1f}°C")
                if status != "critical":
                    status = "warning"
    except (AttributeError, OSError):
        # sensors_temperatures() not available on all platforms
        pass

    # Memory
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    memory_available_mb = memory.available / (1024 * 1024)

    if memory_percent >= settings.memory_warning_percent:
        alerts.append(f"Memory usage high: {memory_percent:.1f}%")
        if status != "critical":
            status = "warning"

    # Disk usage
    disk_usage: Dict[str, float] = {}
    for path in settings.check_paths:
        try:
            usage = psutil.disk_usage(path)
            disk_usage[path] = usage.percent
            if usage.percent >= settings.disk_warning_percent:
                alerts.append(f"Disk usage high on {path}: {usage.percent:.1f}%")
                if status != "critical":
                    status = "warning"
        except (OSError, FileNotFoundError) as e:
            logger.warning("Could not check disk usage for %s: %s", path, e)
            disk_usage[path] = -1.0

    # Build detail summary
    detail_parts = [f"cpu={cpu_percent:.1f}%", f"mem={memory_percent:.1f}%"]
    if cpu_temp is not None:
        detail_parts.append(f"temp={cpu_temp:.1f}°C")
    if disk_usage:
        disk_summary = ", ".join(f"{p}={v:.0f}%" for p, v in disk_usage.items() if v >= 0)
        if disk_summary:
            detail_parts.append(f"disk=[{disk_summary}]")
    if alerts:
        detail_parts.append(f"alerts={len(alerts)}")

    detail = "; ".join(detail_parts)

    result = HealthResult(
        status=status,
        detail=detail,
        cpu_temp=cpu_temp,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        memory_available_mb=round(memory_available_mb, 1),
        disk_usage=disk_usage,
        alerts=alerts,
    )

    logger.info("health.agent completed: %s", detail)
    return result


__all__ = ["run_health_agent", "HealthSettings", "HealthResult"]
