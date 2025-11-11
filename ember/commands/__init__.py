"""Slash command registry."""

from __future__ import annotations

from .config import COMMAND as CONFIG_COMMAND
from .help import COMMAND as HELP_COMMAND
from .status import COMMAND as STATUS_COMMAND

COMMANDS = [
    STATUS_COMMAND,
    HELP_COMMAND,
    CONFIG_COMMAND,
]

__all__ = ["COMMANDS"]
