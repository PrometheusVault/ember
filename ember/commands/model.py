"""Slash command for inspecting or switching llama.cpp models."""

from __future__ import annotations

from pathlib import Path
from typing import List

from ..ai import LlamaSession
from ..slash_commands import SlashCommand, SlashCommandContext, render_rich


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    session: LlamaSession | None = context.metadata.get("llama_session")  # type: ignore[assignment]
    if session is None:
        return "[model] llama session is not available."

    if not args:
        return _render_model_list(session)

    if args[0].lower() == "set" and len(args) >= 2:
        identifier = " ".join(args[1:])
        resolved = session.resolve_model_identifier(identifier)
        if resolved is None or not resolved.exists():
            return f"[model] unable to find model '{identifier}'."
        session.set_model_path(resolved)
        return f"[model] switched to '{resolved}'. The new model will load on the next prompt."

    return "[model] usage: /model or /model set <path-or-name>"


def _render_model_list(session: LlamaSession) -> str:
    current = session.model_path
    models = session.list_available_models()

    if not models:
        body = f"Current model: {current}\n\n(no additional models discovered)"
    else:
        lines = [f"- {path} {'(active)' if path == current else ''}" for path in models]
        if current not in models:
            lines.insert(0, f"- {current} (active)")
        body = "Current model list:\n" + "\n".join(lines)

    return render_rich(lambda console: console.print(body))


COMMAND = SlashCommand(
    name="model",
    description="Show or change the active llama.cpp model.",
    handler=_handler,
    allow_in_planner=False,
)
