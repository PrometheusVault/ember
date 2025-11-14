"""Vault-aware configuration loading for Ember."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Mapping, MutableMapping, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"

DiagnosticLevel = Literal["info", "warning", "error"]
ConfigurationStatus = Literal["ready", "missing", "invalid"]


SchemaSpec = Dict[str, Any]

DEFAULT_PROVISION_PATHS: List[str] = [
    "config",
    "logs",
    "logs/agents",
    "models",
    "plugins",
    "state",
]
DEFAULT_PLUGIN_DIRS: List[str] = [
    "plugins",
    "/usr/local/ember/plugins",
]
DEFAULT_UPDATE_BRANCHES: List[str] = ["main", "master"]


CONFIG_SCHEMA: SchemaSpec = {
    "runtime": {
        "type": dict,
        "schema": {
            "name": {"type": str, "default": "Ember"},
            "auto_restart": {"type": bool, "default": True},
        },
        "default": {},
    },
    "logging": {
        "type": dict,
        "schema": {
            "level": {"type": str, "default": "INFO"},
        },
        "default": {},
    },
    "ui": {
        "type": dict,
        "schema": {
            "verbose": {"type": bool, "default": True},
        },
        "default": {},
    },
    "agents": {
        "type": dict,
        "schema": {
            "enabled": {"type": list, "item_type": str, "default_factory": list},
            "disabled": {"type": list, "item_type": str, "default_factory": list},
        },
        "default": {},
    },
    "provision": {
        "type": dict,
        "schema": {
            "enabled": {"type": bool, "default": True},
            "skip_env": {"type": str, "default": "EMBER_SKIP_PROVISION"},
            "required_paths": {
                "type": list,
                "item_type": str,
                "default_factory": lambda: list(DEFAULT_PROVISION_PATHS),
            },
            "state_file": {"type": str, "default": "state/provision.json"},
        },
        "default": {},
    },
    "network": {
        "type": dict,
        "schema": {
            "enabled": {"type": bool, "default": True},
            "preferred_interfaces": {
                "type": list,
                "item_type": str,
                "default_factory": list,
            },
            "include_loopback": {"type": bool, "default": False},
            "connectivity_checks": {
                "type": list,
                "item_type": str,
                "default_factory": list,
            },
            "connectivity_timeout": {
                "type": (int, float),
                "default": 1.0,
            },
            "dns_paths": {
                "type": list,
                "item_type": str,
                "default_factory": lambda: ["/etc/resolv.conf"],
            },
        },
        "default": {},
    },
    "toolchain": {
        "type": dict,
        "schema": {
            "enabled": {"type": bool, "default": True},
            "manifest": {"type": str, "default": ".toolchain.yml"},
        },
        "default": {},
    },
    "plugin": {
        "type": dict,
        "schema": {
            "enabled": {"type": bool, "default": True},
            "directories": {
                "type": list,
                "item_type": str,
                "default_factory": lambda: list(DEFAULT_PLUGIN_DIRS),
            },
            "manifest_name": {"type": str, "default": "plugin.yml"},
            "include_vault": {"type": bool, "default": True},
        },
        "default": {},
    },
    "test": {
        "type": dict,
        "schema": {
            "enabled": {"type": bool, "default": False},
            "command": {"type": str, "default": "pytest -q"},
            "workdir": {"type": str, "default": "."},
            "report_path": {"type": str, "default": "state/test-agent.json"},
            "timeout": {"type": (int, float), "default": 600},
            "env": {"type": dict, "default": {}},
        },
        "default": {},
    },
    "update": {
        "type": dict,
        "schema": {
            "enabled": {"type": bool, "default": False},
            "allowed_branches": {
                "type": list,
                "item_type": str,
                "default_factory": lambda: list(DEFAULT_UPDATE_BRANCHES),
            },
            "fetch": {"type": bool, "default": False},
        },
        "default": {},
    },
}


@dataclass
class Diagnostic:
    """Represents a configuration validation or loading issue."""

    level: DiagnosticLevel
    message: str
    source: Optional[Path] = None


@dataclass
class ConfigurationBundle:
    """All configuration data Ember needs at runtime."""

    vault_dir: Path
    status: ConfigurationStatus
    merged: Dict[str, Any] = field(default_factory=dict)
    repo_defaults: Dict[str, Any] = field(default_factory=dict)
    vault_overrides: Dict[str, Any] = field(default_factory=dict)
    files_loaded: List[Path] = field(default_factory=list)
    diagnostics: List[Diagnostic] = field(default_factory=list)
    log_path: Optional[Path] = None
    agent_state: Dict[str, Any] = field(default_factory=dict)


def resolve_vault_dir(
    env: Optional[Mapping[str, str]] = None,
    default: str = "/vault",
) -> Path:
    """Resolve the vault path from the environment."""

    env_source = env or os.environ
    raw = env_source.get("VAULT_DIR", default)
    return Path(raw).expanduser()


def load_runtime_configuration(vault_dir: Optional[Path] = None) -> ConfigurationBundle:
    """Load configuration defaults and vault overrides."""

    resolved_vault = vault_dir or resolve_vault_dir()
    diagnostics: List[Diagnostic] = []
    files_loaded: List[Path] = []

    repo_defaults, repo_files = _load_directory_configs(
        DEFAULT_CONFIG_DIR,
        diagnostics,
        label="repo defaults",
    )
    files_loaded.extend(repo_files)

    status: ConfigurationStatus = "ready"
    vault_overrides: Dict[str, Any] = {}

    if not resolved_vault.exists():
        diagnostics.append(
            Diagnostic(
                level="error",
                message=f"Vault directory '{resolved_vault}' does not exist.",
            )
        )
        status = "missing"
    elif not resolved_vault.is_dir():
        diagnostics.append(
            Diagnostic(
                level="error",
                message=f"Vault path '{resolved_vault}' is not a directory.",
            )
        )
        status = "invalid"
    else:
        overrides_dir = resolved_vault / "config"
        vault_overrides, override_files = _load_directory_configs(
            overrides_dir,
            diagnostics,
            label="vault overrides",
        )
        files_loaded.extend(override_files)

    merged = deepcopy(repo_defaults)
    _deep_merge_dicts(merged, vault_overrides)

    _validate_schema(merged, diagnostics)

    if status == "ready" and any(diag.level == "error" for diag in diagnostics):
        status = "invalid"

    return ConfigurationBundle(
        vault_dir=resolved_vault,
        status=status,
        merged=merged,
        repo_defaults=repo_defaults,
        vault_overrides=vault_overrides,
        files_loaded=files_loaded,
        diagnostics=diagnostics,
    )


def _load_directory_configs(
    directory: Path,
    diagnostics: List[Diagnostic],
    label: str,
) -> Tuple[Dict[str, Any], List[Path]]:
    """Load all YAML files from a directory, merging them in order."""

    data: Dict[str, Any] = {}
    loaded_files: List[Path] = []

    if not directory.exists():
        diagnostics.append(
            Diagnostic(
                level="warning",
                message=f"No configuration directory found at '{directory}' ({label}).",
                source=directory,
            )
        )
        return data, loaded_files

    if not directory.is_dir():
        diagnostics.append(
            Diagnostic(
                level="error",
                message=f"Configuration path '{directory}' ({label}) is not a directory.",
                source=directory,
            )
        )
        return data, loaded_files

    yaml_files = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))

    for yaml_file in yaml_files:
        try:
            content = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            diagnostics.append(
                Diagnostic(
                    level="error",
                    message=f"Failed to parse '{yaml_file}': {exc}",
                    source=yaml_file,
                )
            )
            continue

        if content is None:
            loaded_files.append(yaml_file)
            continue

        if not isinstance(content, MutableMapping):
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    message=f"Ignoring '{yaml_file}' because it does not contain a mapping.",
                    source=yaml_file,
                )
            )
            continue

        _deep_merge_dicts(data, dict(content))
        loaded_files.append(yaml_file)

    if not loaded_files:
        diagnostics.append(
            Diagnostic(
                level="info",
                message=f"No YAML files found under '{directory}' ({label}).",
                source=directory,
            )
        )

    return data, loaded_files


def _deep_merge_dicts(dest: MutableMapping[str, Any], source: Mapping[str, Any]) -> None:
    """Recursively merge mapping values."""

    for key, value in source.items():
        if (
            key in dest
            and isinstance(dest[key], MutableMapping)
            and isinstance(value, Mapping)
        ):
            _deep_merge_dicts(dest[key], value)
        else:
            dest[key] = deepcopy(value)


def _default_from_spec(spec: SchemaSpec) -> Any:
    if "default_factory" in spec and callable(spec["default_factory"]):
        return spec["default_factory"]()
    return deepcopy(spec.get("default"))


def _validate_schema(config: Dict[str, Any], diagnostics: List[Diagnostic]) -> None:
    _validate_section(config, CONFIG_SCHEMA, "config", diagnostics)


def _validate_section(
    target: Dict[str, Any],
    schema: SchemaSpec,
    path: str,
    diagnostics: List[Diagnostic],
) -> None:
    if not isinstance(target, dict):
        diagnostics.append(
            Diagnostic(
                level="error",
                message=f"Configuration section '{path}' must be a mapping.",
            )
        )
        return

    for key in list(target.keys()):
        if key not in schema:
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    message=f"Unknown configuration key '{path}.{key}'.",
                )
            )

    for key, spec in schema.items():
        child_path = f"{path}.{key}"
        if key not in target:
            if "default" in spec or "default_factory" in spec:
                target[key] = _default_from_spec(spec)
            continue

        value = target[key]
        expected_type = spec.get("type")

        if expected_type is dict:
            if not isinstance(value, dict):
                diagnostics.append(
                    Diagnostic(
                        level="error",
                        message=f"'{child_path}' must be a mapping.",
                    )
                )
                target[key] = _default_from_spec(spec) or {}
                continue
            _validate_section(value, spec.get("schema", {}), child_path, diagnostics)
        elif expected_type is list:
            if not isinstance(value, list):
                diagnostics.append(
                    Diagnostic(
                        level="error",
                        message=f"'{child_path}' must be a list.",
                    )
                )
                target[key] = _default_from_spec(spec) or []
                continue
            item_type = spec.get("item_type")
            if item_type is not None:
                filtered: List[Any] = []
                for idx, item in enumerate(value):
                    if isinstance(item, item_type):
                        filtered.append(item)
                    else:
                        diagnostics.append(
                            Diagnostic(
                                level="error",
                                message=(
                                    f"'{child_path}[{idx}]' must be of type "
                                    f"{item_type.__name__}."
                                ),
                            )
                        )
                target[key] = filtered
        elif expected_type and not isinstance(value, expected_type):
            if isinstance(expected_type, tuple):
                type_name = ", ".join(t.__name__ for t in expected_type)
            else:
                type_name = expected_type.__name__
            diagnostics.append(
                Diagnostic(
                    level="error",
                    message=f"'{child_path}' must be of type {type_name}.",
                )
            )
            target[key] = _default_from_spec(spec)



__all__ = [
    "ConfigurationBundle",
    "ConfigurationStatus",
    "DEFAULT_CONFIG_DIR",
    "Diagnostic",
    "load_runtime_configuration",
    "resolve_vault_dir",
]
