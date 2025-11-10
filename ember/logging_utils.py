"""Logging helpers for the Ember runtime."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Union

LOG_SUBPATH = Path("logs") / "agents" / "core.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log segment
BACKUP_COUNT = 3


def setup_logging(vault_dir: Path, level: Union[str, int] = logging.WARNING) -> Path:
    """Configure Ember logging to write both to stdout and the vault log file."""

    log_dir = vault_dir / LOG_SUBPATH.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = vault_dir / LOG_SUBPATH

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

    return log_path


def _resolve_level(level: Union[str, int]) -> int:
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.WARNING)
    return int(level)


def _reset_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


__all__ = ["setup_logging", "LOG_SUBPATH"]
