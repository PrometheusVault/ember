"""Vault-aware configuration loading for Ember."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, MutableMapping, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"

DiagnosticLevel = Literal["info", "warning", "error"]
ConfigurationStatus = Literal["ready", "missing", "invalid"]


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


__all__ = [
    "ConfigurationBundle",
    "ConfigurationStatus",
    "DEFAULT_CONFIG_DIR",
    "Diagnostic",
    "load_runtime_configuration",
    "resolve_vault_dir",
]
