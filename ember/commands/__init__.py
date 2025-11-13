"""Slash command registry."""

from __future__ import annotations

from .config import COMMAND as CONFIG_COMMAND
from .help import COMMAND as HELP_COMMAND
from .man import COMMAND as MAN_COMMAND
from .status import COMMAND as STATUS_COMMAND
from .update import COMMAND as UPDATE_COMMAND

COMMANDS = [
    STATUS_COMMAND,
    HELP_COMMAND,
    CONFIG_COMMAND,
    MAN_COMMAND,
    UPDATE_COMMAND,
]

__all__ = ["COMMANDS"]
