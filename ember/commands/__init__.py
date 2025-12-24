"""Slash command registry."""

from __future__ import annotations

from .agents import COMMAND as AGENTS_COMMAND
from .api import COMMAND as API_COMMAND
from .config import COMMAND as CONFIG_COMMAND
from .export import COMMAND as EXPORT_COMMAND
from .help import COMMAND as HELP_COMMAND
from .history import COMMAND as HISTORY_COMMAND
from .man import COMMAND as MAN_COMMAND
from .mesh import COMMAND as MESH_COMMAND
from .model import COMMAND as MODEL_COMMAND
from .rag import COMMAND as RAG_COMMAND
from .status import COMMAND as STATUS_COMMAND
from .sync import COMMAND as SYNC_COMMAND
from .update import COMMAND as UPDATE_COMMAND

COMMANDS = [
    STATUS_COMMAND,
    HELP_COMMAND,
    AGENTS_COMMAND,
    API_COMMAND,
    CONFIG_COMMAND,
    EXPORT_COMMAND,
    HISTORY_COMMAND,
    MAN_COMMAND,
    MESH_COMMAND,
    MODEL_COMMAND,
    RAG_COMMAND,
    SYNC_COMMAND,
    UPDATE_COMMAND,
]

__all__ = ["COMMANDS"]
