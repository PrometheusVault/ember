"""Slash command for exporting session transcripts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

from ..slash_commands import (
    SlashCommand,
    SlashCommandContext,
)


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    """Export session transcript to file."""

    history = context.metadata.get("history", [])
    vault_dir = context.config.vault_dir

    # Parse arguments
    format_type = "txt"
    output_path = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-f", "--format") and i + 1 < len(args):
            format_type = args[i + 1].lower()
            i += 2
        elif arg in ("-o", "--output") and i + 1 < len(args):
            output_path = Path(args[i + 1])
            i += 2
        elif not arg.startswith("-"):
            # Treat as output path
            output_path = Path(arg)
            i += 1
        else:
            i += 1

    if not history:
        return "[export] No commands to export. Run some commands first."

    # Validate format
    if format_type not in ("txt", "json", "md"):
        return f"[export] Unknown format '{format_type}'. Supported: txt, json, md"

    # Default output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exports_dir = vault_dir / "exports"
        try:
            exports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return f"[export] Failed to create exports directory: {e}"
        output_path = exports_dir / f"session_{timestamp}.{format_type}"

    # Make path absolute if relative
    if not output_path.is_absolute():
        output_path = vault_dir / output_path

    # Generate content based on format
    try:
        content = _format_content(history, format_type)
    except Exception as e:
        return f"[export] Failed to format content: {e}"

    # Write file
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"[export] Failed to write file: {e}"

    return f"[export] Session exported to: {output_path}"


def _format_content(history: list, format_type: str) -> str:
    """Format history based on export type."""

    if format_type == "json":
        return json.dumps(
            [{"command": h.command, "output": h.output} for h in history],
            indent=2,
            ensure_ascii=False,
        )

    elif format_type == "md":
        lines = [
            "# Ember Session Export",
            "",
            f"*Exported: {datetime.now().isoformat()}*",
            "",
            f"**Total commands:** {len(history)}",
            "",
            "---",
            "",
        ]
        for i, h in enumerate(history, 1):
            lines.append(f"## {i}. /{h.command}")
            lines.append("")
            lines.append("```")
            lines.append(h.output if h.output else "(no output)")
            lines.append("```")
            lines.append("")
        return "\n".join(lines)

    else:  # txt
        lines = [
            f"Ember Session Export - {datetime.now().isoformat()}",
            "=" * 60,
            f"Total commands: {len(history)}",
            "",
        ]
        for i, h in enumerate(history, 1):
            lines.append(f"[{i}] /{h.command}")
            lines.append("-" * 40)
            lines.append(h.output if h.output else "(no output)")
            lines.append("")
        return "\n".join(lines)


COMMAND = SlashCommand(
    name="export",
    description="Export session transcript. Usage: /export [-f txt|json|md] [-o PATH]",
    handler=_handler,
    allow_in_planner=False,
)
