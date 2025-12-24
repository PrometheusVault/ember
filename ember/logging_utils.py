"""Logging helpers for the Ember runtime."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Optional, Union

LOG_SUBPATH = Path("logs") / "agents" / "core.log"
STRUCTURED_LOG_SUBPATH = Path("logs") / "agents" / "core.jsonl"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log segment
BACKUP_COUNT = 3
REPO_ROOT = Path(__file__).resolve().parent.parent
FALLBACK_ROOT = REPO_ROOT / ".ember_runtime"


class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Include any extra fields attached to the record
        if hasattr(record, "extra") and record.extra:
            log_entry["extra"] = record.extra
        return json.dumps(log_entry)


def setup_logging(
    vault_dir: Path,
    level: Union[str, int] = logging.WARNING,
    structured: bool = True,
    structured_path: Optional[str] = None,
) -> Path:
    """Configure Ember logging with optional structured JSON output.

    Args:
        vault_dir: Path to the vault directory for log storage.
        level: Logging level (string name or int constant).
        structured: Whether to enable structured JSON logging.
        structured_path: Custom path for structured logs (relative to vault_dir).

    Returns:
        Path to the primary (text) log file.
    """
    log_path = _resolve_log_path(vault_dir)

    resolved_level = _resolve_level(level)
    text_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Primary file handler (human-readable text)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(text_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(text_formatter)

    logger = logging.getLogger("ember")
    _reset_handlers(logger)
    logger.setLevel(resolved_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Structured JSON handler (optional)
    if structured:
        json_path = _resolve_structured_log_path(vault_dir, structured_path)
        json_handler = RotatingFileHandler(
            json_path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)

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


def _resolve_structured_log_path(vault_dir: Path, custom_path: Optional[str] = None) -> Path:
    """Resolve the path for structured JSON logs."""
    if custom_path:
        target = vault_dir / custom_path
    else:
        target = vault_dir / STRUCTURED_LOG_SUBPATH

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    except PermissionError:
        fallback = FALLBACK_ROOT / STRUCTURED_LOG_SUBPATH
        fallback.parent.mkdir(parents=True, exist_ok=True)
        print(
            f"[config] Unable to write structured logs under '{vault_dir}'; "
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


__all__ = ["setup_logging", "JSONFormatter", "LOG_SUBPATH", "STRUCTURED_LOG_SUBPATH", "FALLBACK_ROOT"]
