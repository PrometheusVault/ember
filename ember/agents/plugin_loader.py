"""Agent responsible for discovering plugin metadata on disk."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

import yaml

from ..configuration import ConfigurationBundle, Diagnostic, DEFAULT_PLUGIN_DIRS

logger = logging.getLogger("ember.plugin")

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class PluginSettings:
    enabled: bool
    directories: Sequence[Path]
    manifest_name: str
    include_vault: bool

    @classmethod
    def from_bundle(cls, bundle: ConfigurationBundle) -> "PluginSettings":
        raw = bundle.merged.get("plugin", {}) if bundle.merged else {}
        dirs_raw = raw.get("directories", DEFAULT_PLUGIN_DIRS)
        if not dirs_raw:
            dirs_raw = DEFAULT_PLUGIN_DIRS
        directories: List[Path] = []
        for entry in dirs_raw:
            text = str(entry).strip()
            if not text:
                continue
            candidate = Path(text)
            if not candidate.is_absolute():
                candidate = (REPO_ROOT / candidate).resolve()
            directories.append(candidate)
        if not directories:
            directories.append((REPO_ROOT / "plugins").resolve())
        manifest_name = str(raw.get("manifest_name", "plugin.yml")).strip() or "plugin.yml"
        include_vault = bool(raw.get("include_vault", True))
        return cls(
            enabled=bool(raw.get("enabled", True)),
            directories=tuple(dict.fromkeys(directories)),  # preserve order, drop duplicates
            manifest_name=manifest_name,
            include_vault=include_vault,
        )


def run_plugin_agent(bundle: ConfigurationBundle) -> Dict[str, Any]:
    settings = PluginSettings.from_bundle(bundle)

    if not settings.enabled:
        detail = "plugin.agent disabled via configuration."
        logger.info(detail)
        return {"status": "skipped", "detail": detail}

    search_roots: List[Path] = []
    if settings.include_vault:
        search_roots.append(bundle.vault_dir / "plugins")
    search_roots.extend(settings.directories)

    plugins: List[Dict[str, Any]] = []
    for root in search_roots:
        plugins.extend(_scan_plugins(root, settings.manifest_name, bundle))

    detail = f"discovered {len(plugins)} plugin(s)"
    logger.info("plugin.agent completed: %s", detail)

    return {
        "status": "ok",
        "detail": detail,
        "manifest": settings.manifest_name,
        "plugins": plugins,
    }


def _scan_plugins(root: Path, manifest_name: str, bundle: ConfigurationBundle) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not root.exists() or not root.is_dir():
        logger.debug("Plugin path %s missing or not a directory; skipping.", root)
        return results

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        manifest = child / manifest_name
        if not manifest.exists():
            continue
        plugin_info = _load_manifest(child, manifest, bundle)
        plugin_info["source"] = str(root)
        results.append(plugin_info)
    return results


def _load_manifest(plugin_dir: Path, manifest: Path, bundle: ConfigurationBundle) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        message = f"Unable to parse plugin manifest '{manifest}': {exc}"
        bundle.diagnostics.append(
            Diagnostic(level="warning", message=message, source=manifest)
        )
        logger.warning(message)
        return {
            "name": plugin_dir.name,
            "path": str(plugin_dir),
            "manifest": str(manifest),
            "status": "invalid",
            "detail": "manifest parse error",
        }

    name = str(data.get("name", plugin_dir.name)).strip()
    if not name:
        message = f"Plugin manifest '{manifest}' is missing a name."
        bundle.diagnostics.append(
            Diagnostic(level="warning", message=message, source=manifest)
        )
        logger.warning(message)
        return {
            "name": plugin_dir.name,
            "path": str(plugin_dir),
            "manifest": str(manifest),
            "status": "invalid",
            "detail": "missing name",
        }

    entrypoint = data.get("entrypoint")
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        hooks = {str(k): str(v) for k, v in hooks.items()}
    elif hooks is not None:
        hooks = None

    return {
        "name": name,
        "version": data.get("version"),
        "description": data.get("description"),
        "entrypoint": entrypoint,
        "hooks": hooks,
        "path": str(plugin_dir),
        "manifest": str(manifest),
        "status": "ready",
    }


__all__ = ["run_plugin_agent", "PluginSettings"]
