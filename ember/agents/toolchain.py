"""Toolchain readiness agent."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import logging
import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Any, Dict, List, Sequence

import yaml

from ..configuration import ConfigurationBundle, Diagnostic

logger = logging.getLogger("ember.toolchain")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / ".toolchain.yml"


@dataclass
class ToolchainSettings:
    """Runtime knobs for the toolchain agent."""

    enabled: bool
    manifest: Path

    @classmethod
    def from_bundle(cls, bundle: ConfigurationBundle) -> "ToolchainSettings":
        raw = bundle.merged.get("toolchain", {}) if bundle.merged else {}
        manifest_raw = str(raw.get("manifest", DEFAULT_MANIFEST)).strip()
        manifest = Path(manifest_raw) if manifest_raw else DEFAULT_MANIFEST
        if not manifest.is_absolute():
            manifest = (REPO_ROOT / manifest).resolve()
        return cls(
            enabled=bool(raw.get("enabled", True)),
            manifest=manifest,
        )


def run_toolchain_agent(bundle: ConfigurationBundle) -> Dict[str, Any]:
    """Check command/python/file/env requirements defined in .toolchain.yml."""

    settings = ToolchainSettings.from_bundle(bundle)

    if not settings.enabled:
        detail = "toolchain.agent disabled via configuration."
        logger.info(detail)
        return {"status": "skipped", "detail": detail}

    try:
        manifest = _load_manifest(settings.manifest)
    except FileNotFoundError:
        message = f"Toolchain manifest '{settings.manifest}' not found."
        bundle.diagnostics.append(
            Diagnostic(level="error", message=message, source=settings.manifest)
        )
        logger.error(message)
        return {
            "status": "error",
            "detail": message,
            "manifest": str(settings.manifest),
        }
    except yaml.YAMLError as exc:
        message = f"Unable to parse toolchain manifest '{settings.manifest}': {exc}"
        bundle.diagnostics.append(
            Diagnostic(level="error", message=message, source=settings.manifest)
        )
        logger.error(message)
        return {
            "status": "error",
            "detail": message,
            "manifest": str(settings.manifest),
        }

    commands = _check_commands(manifest.get("commands", []))
    python = _check_python_modules(manifest.get("python", []))
    files = _check_files(manifest.get("files", []))
    env = _check_env_vars(manifest.get("env", []))

    missing_required = any(not item["available"] and not item["optional"] for item in commands)
    missing_required |= any(not item["available"] and not item["optional"] for item in python)
    missing_required |= any(not item["available"] and not item["optional"] for item in files)
    missing_required |= any(not item["available"] and not item["optional"] for item in env)

    status = "ok" if not missing_required else "degraded"
    detail = _summary(commands, python, files, env)

    logger.info("toolchain.agent completed: %s", detail)

    return {
        "status": status,
        "detail": detail,
        "manifest": str(settings.manifest),
        "commands": commands,
        "python": python,
        "files": files,
        "env": env,
    }


def _load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise yaml.YAMLError("Top-level manifest must be a mapping.")
    return data


def _check_commands(raw: Sequence[Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for entry in raw or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        optional = bool(entry.get("optional", False))
        description = str(entry.get("description", ""))
        version_cmd = entry.get("version_command")
        available_path = shutil.which(name)
        version = None
        if available_path and version_cmd:
            version = _capture_version(version_cmd)
        result = {
            "name": name,
            "optional": optional,
            "available": bool(available_path),
            "path": available_path,
            "description": description,
            "version": version,
        }
        results.append(result)
    return results


def _check_python_modules(raw: Sequence[Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for entry in raw or []:
        module = entry
        optional = False
        description = ""
        if isinstance(entry, dict):
            module = entry.get("module")
            optional = bool(entry.get("optional", False))
            description = str(entry.get("description", ""))
        if not module:
            continue
        module_name = str(module).strip()
        if not module_name:
            continue
        available = importlib.util.find_spec(module_name) is not None
        results.append(
            {
                "module": module_name,
                "optional": optional,
                "available": available,
                "description": description,
            }
        )
    return results


def _check_files(raw: Sequence[Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for entry in raw or []:
        path_value = entry
        optional = False
        description = ""
        if isinstance(entry, dict):
            path_value = entry.get("path")
            optional = bool(entry.get("optional", False))
            description = str(entry.get("description", ""))
        if not path_value:
            continue
        path_str = str(path_value).strip()
        if not path_str:
            continue
        candidate = Path(path_str)
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / candidate).resolve()
        available = candidate.exists()
        results.append(
            {
                "path": str(candidate),
                "optional": optional,
                "available": available,
                "description": description,
            }
        )
    return results


def _check_env_vars(raw: Sequence[Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for entry in raw or []:
        name = entry
        optional = False
        description = ""
        if isinstance(entry, dict):
            name = entry.get("name")
            optional = bool(entry.get("optional", False))
            description = str(entry.get("description", ""))
        if not name:
            continue
        env_name = str(name).strip()
        if not env_name:
            continue
        value = os.environ.get(env_name)
        results.append(
            {
                "name": env_name,
                "optional": optional,
                "available": value is not None,
                "value": value,
                "description": description,
            }
        )
    return results


def _capture_version(command_str: str) -> str | None:
    try:
        args = shlex.split(command_str)
        completed = subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return completed.stdout.strip()
    except Exception as exc:  # pragma: no cover - best-effort diagnostic
        logger.debug("Version command '%s' failed: %s", command_str, exc)
    return None


def _summary(
    commands: Sequence[Dict[str, Any]],
    python: Sequence[Dict[str, Any]],
    files: Sequence[Dict[str, Any]],
    env: Sequence[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    if commands:
        required = sum(1 for item in commands if not item["optional"])
        ok = sum(1 for item in commands if item["available"] and not item["optional"])
        parts.append(f"commands {ok}/{required} required ready")
    if python:
        required = sum(1 for item in python if not item["optional"])
        ok = sum(1 for item in python if item["available"] and not item["optional"])
        parts.append(f"python {ok}/{required} modules ready")
    if files:
        required = sum(1 for item in files if not item["optional"])
        ok = sum(1 for item in files if item["available"] and not item["optional"])
        parts.append(f"files {ok}/{required} present")
    if env:
        required = sum(1 for item in env if not item["optional"])
        ok = sum(1 for item in env if item["available"] and not item["optional"])
        parts.append(f"env {ok}/{required} set")
    return ", ".join(parts) if parts else "no toolchain requirements defined"


__all__ = ["run_toolchain_agent", "ToolchainSettings"]
