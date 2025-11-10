"""Tests for logging utilities."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ember.logging_utils import setup_logging


def _reset_logger() -> logging.Logger:
    logger = logging.getLogger("ember")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    return logger


def test_setup_logging_creates_rotating_file(tmp_path: Path):
    logger = _reset_logger()
    log_path = setup_logging(tmp_path, level="INFO")

    assert log_path == tmp_path / "logs" / "agents" / "core.log"
    assert log_path.exists()

    file_handlers = [
        handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    assert file_handlers[0].baseFilename == str(log_path)


def test_setup_logging_is_idempotent(tmp_path: Path):
    logger = _reset_logger()
    setup_logging(tmp_path, level="INFO")
    handler_count = len(logger.handlers)

    setup_logging(tmp_path, level="INFO")
    assert len(logger.handlers) == handler_count
