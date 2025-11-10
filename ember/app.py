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
try:
    import readline
except ImportError:  # pragma: no cover
    readline = None
from textwrap import dedent
from typing import Callable, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .ai import (
    CommandExecutionLog,
    DocumentationContext,
    LlamaPlan,
    LlamaSession,
)
from .configuration import (
    ConfigurationBundle,
    Diagnostic,
    load_runtime_configuration,
)
from .logging_utils import setup_logging
from .slash_commands import (
    CommandRouter,
    SlashCommand,
    SlashCommandContext,
    render_help_table,
    render_rich,
)

VAULT_DIR = Path(os.environ.get("VAULT_DIR", "/vault")).expanduser()
EMBER_MODE = os.environ.get("EMBER_MODE", "DEV (Docker)")
REPO_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("ember")


def _log_path_within_vault(log_path: Path, vault_dir: Path) -> bool:
    try:
        log_path.relative_to(vault_dir)
        return True
    except ValueError:
        return False


def print_banner() -> None:
    """Print the runtime header so operators know where Ember is pointed."""

    banner = dedent(
        f"""
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃  Prometheus Vault – Ember (dev stub)      ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
        Vault dir : {VAULT_DIR}
        Mode      : {EMBER_MODE}
        """
    ).strip()
    print(banner)
    print()


def build_router(config: ConfigurationBundle) -> CommandRouter:
    """Seed the router with placeholder commands."""

    router = CommandRouter(config)
    router.register(
        SlashCommand(
            name="status",
            description="Show vault, logging, and configuration diagnostics.",
            handler=status_command,
        )
    )
    router.register(
        SlashCommand(
            name="help",
            description="List available slash commands.",
            handler=help_command,
        )
    )
    return router


def status_command(context: SlashCommandContext, _: List[str]) -> str:
    """Pretty runtime status via Rich tables."""

    config = context.config
    info = Table.grid(padding=(0, 2))
    info.add_row("Vault", str(config.vault_dir))
    info.add_row("Status", config.status)
    info.add_row("Config files", str(len(config.files_loaded)))
    info.add_row("Log path", str(config.log_path or "(not initialized)"))
    info.add_row("Mode", EMBER_MODE)

    def _render(console: Console) -> None:
        console.print(Panel(info, title="Runtime Status", border_style="green"))
        if config.diagnostics:
            diag_table = Table(show_header=True, header_style="bold red")
            diag_table.add_column("Level", style="red")
            diag_table.add_column("Message")
            diag_table.add_column("Source", overflow="fold")
            for diag in config.diagnostics:
                source = str(diag.source or config.vault_dir)
                diag_table.add_row(diag.level.upper(), diag.message, source)
            console.print(Panel(diag_table, title="Diagnostics", border_style="red"))

    return render_rich(_render)


def help_command(context: SlashCommandContext, _: List[str]) -> str:
    """Rich-formatted help table."""

    return render_help_table(context.router.commands())


def emit_configuration_report(config: ConfigurationBundle) -> None:
    """Print diagnostics so operators can correct issues quickly."""

    if not config.diagnostics:
        print(
            f"[config] Loaded {len(config.files_loaded)} file(s) "
            f"from repo and vault config directories."
        )
        return

    print("[config] Diagnostics:")
    for diag in config.diagnostics:
        prefix = diag.source or config.vault_dir
        print(f"  - ({diag.level.upper()}) {diag.message} [{prefix}]")


def configure_autocomplete(router: CommandRouter) -> None:
    """Enable readline tab completion for slash commands."""

    if readline is None:
        return

    commands = list(router.command_names)

    def completer(text: str, state: int):
        buffer = readline.get_line_buffer()
        if not buffer.startswith("/"):
            return None
        fragment = text[1:] if text.startswith("/") else text
        matches = [f"/{cmd}" for cmd in commands if cmd.startswith(fragment)]
        if state < len(matches):
            return matches[state]
        return None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t")


def execute_cli_command(
    command_line: str,
    router: CommandRouter,
    llama_session: LlamaSession,
    history: List[CommandExecutionLog],
) -> str:
    """Helper that executes an Ember CLI command and records the output."""

    stripped = command_line.strip()
    if not stripped:
        return ""

    parts = stripped.split()
    command, args = parts[0], parts[1:]
    result = router.handle(command, args)
    print(result)

    log_entry = CommandExecutionLog(command=stripped, output=result)
    history.append(log_entry)
    llama_session.record_execution(log_entry)
    logger.info("Executed CLI command: %s", stripped)
    return result


def bootstrap_llama_session(
    history: List[CommandExecutionLog],
    router: CommandRouter,
) -> tuple[LlamaSession, int]:
    """Load documentation context and return a prepped llama session plus doc count."""

    doc_context = DocumentationContext(repo_root=REPO_ROOT)
    snippets = doc_context.load()
    llama_session = LlamaSession(
        command_history=history,
        command_names=list(router.command_names),
    )
    llama_session.prime_with_docs(snippets)
    return llama_session, len(snippets)


def main() -> None:
    """Entry point for `python -m ember`."""

    log_level_name = os.environ.get("EMBER_LOG_LEVEL", "WARNING").upper()
    console = Console()
    print_banner()
    config_bundle = load_runtime_configuration(VAULT_DIR)
    log_path = setup_logging(config_bundle.vault_dir, log_level_name)
    config_bundle.log_path = log_path
    if not _log_path_within_vault(log_path, config_bundle.vault_dir):
        config_bundle.diagnostics.append(
            Diagnostic(
                level="warning",
                message=(
                    "Vault log directory is not writable; "
                    f"logging to fallback path '{log_path}'."
                ),
                source=log_path,
            )
        )
    emit_configuration_report(config_bundle)
    logger.info("Logging initialized at %s", log_path)
    router = build_router(config_bundle)
    configure_autocomplete(router)
    history: List[CommandExecutionLog] = []
    llama_session, doc_count = bootstrap_llama_session(history, router)
    show_runtime_overview(console, llama_session, doc_count)

    print("Type '/help' for runtime commands; any other text is sent to llama.cpp.")
    print("Use 'quit' or 'exit' to leave.\n")

    while True:
        try:
            raw_line = input("> ")
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

        if line.startswith("/"):
            command_line = line[1:]
            if command_line.lower() in {"quit", "exit"}:
                print("[Goodbye]")
                break
            execute_cli_command(command_line, router, llama_session, history)
            continue

        logger.info("User prompt: %s", line)
        status_text = f"[cyan]Thinking: {line[:40]}{'…' if len(line) > 40 else ''}"
        with console.status(status_text, spinner="dots"):
            plan: LlamaPlan = llama_session.plan(line)

        if plan.commands:
            show_plan_summary(console, plan)
            tool_chunks = []
            for planned_command in plan.commands:
                result = execute_cli_command(planned_command, router, llama_session, history)
                tool_chunks.append(f"/{planned_command}\n{result}")
            tool_context = "\n\n".join(tool_chunks)
            final_response = llama_session.respond(line, tool_context)
            show_final_response(console, final_response, plan.commands)
        else:
            show_final_response(console, plan.response, [])
def show_runtime_overview(
    console: Console,
    session: LlamaSession,
    doc_count: int,
) -> None:
    """Render a small panel summarizing current runtime settings."""

    table = Table.grid(padding=(0, 1))
    table.add_row("Model", str(session.model_path.name))
    table.add_row("Max tokens", str(session.max_tokens))
    table.add_row("Threads", str(session.n_threads))
    table.add_row("Docs cached", str(doc_count))
    commands_preview = ", ".join(f"/{cmd}" for cmd in session.command_names[:6])
    if len(session.command_names) > 6:
        commands_preview += " …"
    table.add_row("Commands", commands_preview or "(none)")

    console.print(Panel(table, title="Ember Runtime", border_style="cyan"))


def show_plan_summary(console: Console, plan: LlamaPlan) -> None:
    """Display the planner's intent before tools run."""

    commands_text = ", ".join(f"/{cmd}" for cmd in plan.commands) or "None"
    preview = plan.response.strip() or "(planner provided no notes)"

    console.print(
        Panel(
            f"[bold]Planner notes[/bold]\n{preview}\n\n[bold]Commands to run[/bold]\n{commands_text}",
            border_style="yellow",
            title="Planner",
        )
    )


def show_final_response(
    console: Console,
    response: str,
    commands_run: List[str],
) -> None:
    """Render the final conversational answer."""

    commands_text = ", ".join(f"/{cmd}" for cmd in commands_run) or "None"
    preview = response.strip() or "(no response)"
    console.print(f"[bold cyan]Ember>[/] {preview}")
    if commands_run:
        console.print(
            Panel(
                f"[bold]Commands run[/bold]\n{commands_text}",
                border_style="blue",
                title="Tools",
            )
        )
