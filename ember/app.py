# ember/app.py
"""
Interactive development stub for the Ember runtime loop.

The module keeps the CLI simple while leaving placeholder hooks for the future
planner/agent pipeline described in AGENTS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from textwrap import dedent
from typing import Callable, Dict, List

from rich.console import Console

from .ai import (
    CommandExecutionLog,
    DocumentationContext,
    LlamaPlan,
    LlamaSession,
)

VAULT_DIR = Path(os.environ.get("VAULT_DIR", "/vault")).expanduser()
EMBER_MODE = os.environ.get("EMBER_MODE", "DEV (Docker)")
REPO_ROOT = Path(__file__).resolve().parent.parent
CommandHandler = Callable[[List[str]], str]
logger = logging.getLogger("ember")


def print_banner() -> None:
    """Print the runtime header so operators know where Ember is pointed."""

    banner = dedent(
        f"""
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃  Prometheus Vault – Ember (dev stub)     ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
        Vault dir : {VAULT_DIR}
        Mode      : {EMBER_MODE}
        """
    ).strip()
    print(banner)
    print()


def load_configuration(vault_dir: Path) -> Dict[str, str]:
    """
    Placeholder config loader.

    Future state: read YAML under `config/` and the selected vault. For now we
    just report whether the directory exists so operators can spot misconfigurations.
    """

    status = "ready" if vault_dir.exists() else "missing"
    return {"vault_path": str(vault_dir), "vault_status": status}


@dataclass
class CommandRouter:
    """Dispatches CLI commands to registered handlers."""

    handlers: Dict[str, CommandHandler] = field(default_factory=dict)

    def register(self, command: str, handler: CommandHandler) -> None:
        """Attach a handler for a lower-case command keyword."""

        self.handlers[command.lower()] = handler

    def handle(self, command: str, args: List[str]) -> str:
        """
        Route the command to the matching handler.

        Returning strings keeps the transport simple for now; in the future the
        handler will likely emit structured JSON for the UI/web API.
        """

        handler = self.handlers.get(command.lower())
        if handler is None:
            return (
                f"[todo] '{command}' is not wired yet. "
                "Documented handlers will populate here as agents land."
            )
        return handler(args)


def build_router(config: Dict[str, str]) -> CommandRouter:
    """Seed the router with placeholder commands."""

    router = CommandRouter()

    def status_handler(_: List[str]) -> str:
        return (
            "[status] vault={vault_path} ({vault_status}) "
            "future: include agent + plugin health"
        ).format(**config)

    router.register("status", status_handler)
    router.register("help", lambda _: "Commands: status, help, quit")
    return router


def execute_cli_command(
    command_line: str,
    router: CommandRouter,
    llama_session: LlamaSession,
    history: List[CommandExecutionLog],
) -> None:
    """Helper that executes an Ember CLI command and records the output."""

    stripped = command_line.strip()
    if not stripped:
        return

    parts = stripped.split()
    command, args = parts[0], parts[1:]
    result = router.handle(command, args)
    print(result)

    log_entry = CommandExecutionLog(command=stripped, output=result)
    history.append(log_entry)
    llama_session.record_execution(log_entry)
    logger.info("Executed CLI command: %s", stripped)


def bootstrap_llama_session(history: List[CommandExecutionLog]) -> LlamaSession:
    """Load documentation context and return a prepped llama session."""

    doc_context = DocumentationContext(repo_root=REPO_ROOT)
    snippets = doc_context.load()
    llama_session = LlamaSession(command_history=history)
    llama_session.prime_with_docs(snippets)
    return llama_session


def main() -> None:
    """Entry point for `python -m ember`."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    console = Console()
    print_banner()
    config = load_configuration(VAULT_DIR)
    router = build_router(config)
    history: List[CommandExecutionLog] = []
    llama_session = bootstrap_llama_session(history)

    print("Type ':help' for runtime commands; any other text is sent to llama.cpp.")
    print("Use 'quit' or 'exit' to leave.\n")

    while True:
        try:
            raw_line = input("EMBER> ")
        except (EOFError, KeyboardInterrupt):
            print("\n[Exiting Ember]")
            break

        if raw_line == "\x0c":  # Ctrl-L (form feed)
            print("\033[2J\033[H", end="")
            print_banner()
            continue

        line = raw_line.strip()

        if line.lower() in {"quit", "exit"}:
            print("[Goodbye]")
            break

        if not line:
            continue

        if line.startswith(":"):
            execute_cli_command(line[1:], router, llama_session, history)
            continue

        logger.info("User prompt: %s", line)
        with console.status("[cyan]Ember is thinking…", spinner="dots"):
            plan: LlamaPlan = llama_session.plan(line)
        print(plan.response)

        for planned_command in plan.commands:
            execute_cli_command(planned_command, router, llama_session, history)
