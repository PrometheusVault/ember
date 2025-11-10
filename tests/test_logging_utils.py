"""Tests for logging utilities."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ember import logging_utils


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
    log_path = logging_utils.setup_logging(tmp_path, level="INFO")

    assert log_path == tmp_path / "logs" / "agents" / "core.log"
    assert log_path.exists()

    file_handlers = [
        handler for handler in logger.handlers if isinstance(handler, RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    assert file_handlers[0].baseFilename == str(log_path)


def test_setup_logging_is_idempotent(tmp_path: Path):
    logger = _reset_logger()
    logging_utils.setup_logging(tmp_path, level="INFO")
    handler_count = len(logger.handlers)

    logging_utils.setup_logging(tmp_path, level="INFO")
    assert len(logger.handlers) == handler_count


def test_setup_logging_falls_back_when_permission_denied(tmp_path: Path, monkeypatch):
    logger = _reset_logger()
    vault_dir = tmp_path / "vault"
    primary_parent = vault_dir / "logs" / "agents"
    original_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if str(self).startswith(str(primary_parent)):
            raise PermissionError
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    fallback_root = tmp_path / "fallback"
    monkeypatch.setattr(logging_utils, "FALLBACK_ROOT", fallback_root)

    log_path = logging_utils.setup_logging(vault_dir, level="INFO")
    expected = fallback_root / "logs" / "agents" / "core.log"

    assert log_path == expected
    assert expected.exists()
