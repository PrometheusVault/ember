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
from shutil import get_terminal_size
from typing import Callable, Dict, List, Sequence

from rich.console import Console
from rich.markdown import Markdown
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.text import Text

from .agents import REGISTRY
from .ai import (
    CommandExecutionLog,
    DocumentationContext,
    LlamaPlan,
    LlamaSession,
)
from .commands import COMMANDS
from .configuration import (
    ConfigurationBundle,
    Diagnostic,
    load_runtime_configuration,
)
from .logging_utils import setup_logging
from .slash_commands import CommandRouter, CommandSource

VAULT_DIR = Path(os.environ.get("VAULT_DIR", "/vault")).expanduser()
EMBER_MODE = os.environ.get("EMBER_MODE", "DEV (Docker)")
REPO_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("ember")
TRUE_STRINGS = {"1", "true", "yes", "on"}
FALSE_STRINGS = {"0", "false", "no", "off"}


class _NoOpStatus:
    """Fallback status handle when UI verbosity is disabled."""

    def update(self, *_args, **_kwargs) -> None:  # pragma: no cover - trivial
        pass

def _log_path_within_vault(log_path: Path, vault_dir: Path) -> bool:
    try:
        log_path.relative_to(vault_dir)
        return True
    except ValueError:
        return False


def print_banner() -> None:
    """Print the runtime header so operators know where Ember is pointed."""

    terminal_width = get_terminal_size(fallback=(80, 24)).columns

    def _wide_banner() -> str:
        inner_width = 78
        title = "PROMETHEUS VAULT :: EMBER"
        slogan = "survive ◇ record ◇ rebuild"

        def _line(content: str = "") -> str:
            return f"║{content.center(inner_width)}║"

        lines = [
            "╔" + "═" * inner_width + "╗",
            _line(),
            _line(title),
            _line(slogan),
            _line(),
            "╚" + "═" * inner_width + "╝",
        ]
        return "\n".join(lines)

    def _narrow_banner() -> str:
        return "Prometheus Vault :: Ember"

    banner = _wide_banner() if terminal_width >= 80 else _narrow_banner()

    print(banner)
    print()


def _parse_env_flag(value: str, *, default: bool = True) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_STRINGS:
        return True
    if normalized in FALSE_STRINGS:
        return False
    return default


def _resolve_ui_verbose(config_bundle: ConfigurationBundle) -> bool:
    """Resolve whether the CLI should display the full HUD or a quiet view."""

    env_value = os.environ.get("EMBER_UI_VERBOSE")
    if env_value is not None:
        return _parse_env_flag(env_value)

    merged = config_bundle.merged or {}
    ui_cfg = merged.get("ui") or {}
    verbose_setting = ui_cfg.get("verbose")
    if verbose_setting is None:
        return True
    return bool(verbose_setting)


def _format_command_block(
    commands: Sequence[str],
    *,
    limit: int | None = None,
    bullet: bool = False,
) -> str:
    if not commands:
        return "(none)"
    subset = list(commands if limit is None else commands[:limit])
    prefix = "• " if bullet else ""
    lines = [f"{prefix}/{cmd}" for cmd in subset]
    if limit is not None and len(commands) > limit:
        lines.append("…")
    return "\n".join(lines)


def build_router(config: ConfigurationBundle) -> CommandRouter:
    """Seed the router with placeholder commands."""

    router = CommandRouter(
        config,
        metadata={
            "mode": EMBER_MODE,
            "repo_root": str(REPO_ROOT),
        },
    )
    for command in COMMANDS:
        router.register(command)
    return router


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
    *,
    source: CommandSource = CommandSource.USER,
    suppress_output: bool = False,
) -> str:
    """Helper that executes an Ember CLI command and records the output."""

    stripped = command_line.strip()
    if not stripped:
        return ""

    parts = stripped.split()
    command, args = parts[0], parts[1:]
    result = router.handle(command, args, source=source)
    if not suppress_output:
        print(result)

    log_entry = CommandExecutionLog(command=stripped, output=result)
    history.append(log_entry)
    llama_session.record_execution(log_entry)
    logger.info("Executed CLI command: %s", stripped)
    return result


def bootstrap_llama_session(
    history: List[CommandExecutionLog],
    router: CommandRouter,
    vault_dir: Path | None = None,
) -> tuple[LlamaSession, int]:
    """Load documentation context and return a prepped llama session plus doc count."""

    doc_context = DocumentationContext(repo_root=REPO_ROOT, vault_dir=vault_dir)
    snippets = doc_context.load()
    llama_session = LlamaSession(
        command_history=history,
        command_names=list(router.planner_command_names),
    )
    llama_session.prime_with_docs(snippets)
    return llama_session, len(snippets)


def main() -> None:
    """Entry point for `python -m ember`."""

    console = Console()
    config_bundle = load_runtime_configuration(VAULT_DIR)
    ui_verbose = _resolve_ui_verbose(config_bundle)
    if ui_verbose:
        print_banner()
    else:
        print(f"[Ember] {EMBER_MODE} ready (quiet mode)")
        print()

    configured_level = (
        (config_bundle.merged.get("logging", {}) or {}).get("level")
        if config_bundle.merged
        else None
    )
    env_level = os.environ.get("EMBER_LOG_LEVEL")
    log_level_name = (env_level or configured_level or "WARNING").upper()
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
    bootstrap_agents(config_bundle)
    logger.info("Logging initialized at %s", log_path)
    logger.info("UI verbosity: %s", "enabled" if ui_verbose else "disabled")
    router = build_router(config_bundle)
    configure_autocomplete(router)
    history: List[CommandExecutionLog] = []
    llama_session, _ = bootstrap_llama_session(history, router, config_bundle.vault_dir)
    router.metadata["llama_session"] = llama_session

    while True:
        try:
            raw_line = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\n[Exiting Ember]")
            break

        if raw_line == "\x0c":  # Ctrl-L (form feed)
            print("\033[2J\033[H", end="")
            if ui_verbose:
                print_banner()
            else:
                print(f"[Ember] {EMBER_MODE} ready (quiet mode)")
                print()
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
            execute_cli_command(command_line, router, llama_session, history, source=CommandSource.USER)
            continue

        logger.info("User prompt: %s", line)
        if ui_verbose:
            console.print()
            console.print(Text("[Thinking] Planning next steps…", style="cyan"))
        status_cm: Status | None = console.status("[cyan]Planning…", spinner="dots") if ui_verbose else None
        status = status_cm.__enter__() if status_cm else _NoOpStatus()
        try:
            plan: LlamaPlan = llama_session.plan(line)

            if plan.commands:
                if ui_verbose:
                    show_plan_summary(console, plan)
                tool_chunks = []
                for planned_command in plan.commands:
                    if ui_verbose:
                        console.print(Text(f"[Action] Running /{planned_command}", style="magenta"))
                    status.update(f"[cyan]Running /{planned_command}")
                    result = execute_cli_command(
                        planned_command,
                        router,
                        llama_session,
                        history,
                        source=CommandSource.PLANNER,
                        suppress_output=True,
                    )
                    tool_chunks.append(f"/{planned_command}\n{result}")
                status.update("[cyan]Generating response…")
                tool_context = "\n\n".join(tool_chunks)
                if ui_verbose:
                    console.print(Text("[Thinking] Drafting final response…", style="cyan"))
                final_response = llama_session.respond(line, tool_context)
                show_final_response(console, final_response, plan.commands, verbose=ui_verbose)
            else:
                status.update("[cyan]Generating response…")
                if ui_verbose:
                    console.print(Text("[Thinking] Drafting final response…", style="cyan"))
                show_final_response(console, plan.response, [], verbose=ui_verbose)
        finally:
            if status_cm:
                status_cm.__exit__(None, None, None)


def bootstrap_agents(config_bundle: ConfigurationBundle) -> None:
    """Invoke enabled agents that should run during startup."""

    results = REGISTRY.run(config_bundle, trigger="bootstrap")
    if results:
        config_bundle.agent_state.update(results)


def show_runtime_overview(
    console: Console,
    session: LlamaSession,
    doc_count: int,
) -> None:
    """Render a small panel summarizing current runtime settings."""

    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(style="bold", no_wrap=True)
    table.add_column()
    table.add_row("Model", str(session.model_path.name))
    table.add_row("Max tokens", str(session.max_tokens))
    table.add_row("Threads", str(session.n_threads))
    table.add_row("Docs cached", str(doc_count))
    table.add_row(
        "Commands",
        _format_command_block(session.command_names, limit=5),
    )

    console.print("[Runtime] Ember configuration")
    console.print(table)


def show_plan_summary(console: Console, plan: LlamaPlan) -> None:
    """Display the planner's intent before tools run."""

    preview = plan.response.strip() or "(planner provided no notes)"
    body = Table.grid(expand=True, padding=(0, 1))
    body.add_column(style="bold", no_wrap=True)
    body.add_column()
    body.add_row("Notes", preview)
    body.add_row(
        "Commands",
        _format_command_block(plan.commands, bullet=True),
    )

    console.print("[Planner]")
    console.print(body)


def show_final_response(
    console: Console,
    response: str,
    commands_run: List[str],
    *,
    verbose: bool = True,
) -> None:
    """Render the final conversational answer."""

    preview = response.strip() or "I was unable to generate a response, but I'm still ready to assist."
    if verbose:
        console.print()
        console.print(Text("[Ember]", style="bold cyan"))
        for line in preview.splitlines():
            console.print(line)
        if commands_run:
            console.print("\n[Tools]")
            for cmd in commands_run:
                console.print(f"- /{cmd}")
        console.print()
    else:
        console.print()
        console.print(preview)
        if commands_run:
            console.print()
            summary = ", ".join(f"/{cmd}" for cmd in commands_run)
            console.print(f"[tools] {summary}")
        console.print()
