"""Logging helpers for the Ember runtime."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Union

LOG_SUBPATH = Path("logs") / "agents" / "core.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log segment
BACKUP_COUNT = 3
REPO_ROOT = Path(__file__).resolve().parent.parent
FALLBACK_ROOT = REPO_ROOT / ".ember_runtime"


def setup_logging(vault_dir: Path, level: Union[str, int] = logging.WARNING) -> Path:
    """Configure Ember logging to write both to stdout and the vault log file."""

    log_path = _resolve_log_path(vault_dir)

    resolved_level = _resolve_level(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger("ember")
    _reset_handlers(logger)
    logger.setLevel(resolved_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    _silence_third_party()
    return log_path


def _resolve_level(level: Union[str, int]) -> int:
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.WARNING)
    return int(level)


def _resolve_log_path(vault_dir: Path) -> Path:
    primary = vault_dir / LOG_SUBPATH
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        return primary
    except PermissionError:
        fallback = FALLBACK_ROOT / LOG_SUBPATH
        fallback.parent.mkdir(parents=True, exist_ok=True)
        print(
            f"[config] Unable to write logs under '{vault_dir}'; "
            f"falling back to '{fallback.parent}'.",
            file=sys.stderr,
        )
        return fallback


def _reset_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def _silence_third_party() -> None:
    # llama_cpp can be quite verbose; keep it at WARNING unless the operator
    # explicitly raises logging globally.
    logging.getLogger("llama_cpp").setLevel(logging.WARNING)


__all__ = ["setup_logging", "LOG_SUBPATH", "FALLBACK_ROOT"]
