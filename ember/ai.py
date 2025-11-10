# ember/ai.py
"""
Placeholders for llama.cpp interaction and documentation context gathering.

These helpers keep the main app loop tidy while making it obvious where the
final planner/runtime glue will land once llama.cpp bindings are available on
the Raspberry Pi 5 images.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
from textwrap import dedent
from typing import Iterable, List, Sequence


DEFAULT_DOC_PATHS = (
    Path("README.md"),
    Path("AGENTS.md"),
    Path("docs/ROADMAP.md"),
)
COMMAND_PATTERN = re.compile(r"\[\[COMMAND:(.*?)\]\]")
logger = logging.getLogger(__name__)


def _default_llama_bin() -> Path:
    env_path = os.environ.get("LLAMA_CPP_BIN")
    if env_path:
        return Path(env_path).expanduser()
    return Path("/opt/llama.cpp/llama-cli")


def _default_model_path() -> Path:
    env_path = os.environ.get("LLAMA_CPP_MODEL")
    if env_path:
        return Path(env_path).expanduser()
    return Path("/opt/llama.cpp/models/ember.bin")


@dataclass
class DocumentationSnippet:
    """Represents a short slice of a documentation file for prompting."""

    source: str
    excerpt: str

    def headline(self, max_chars: int = 96) -> str:
        """Return a single-line preview for logging/debugging."""

        sanitized = " ".join(self.excerpt.split())
        return sanitized[:max_chars]


@dataclass
class DocumentationContext:
    """Loads repo documentation to ground llama.cpp responses."""

    repo_root: Path
    doc_paths: Sequence[Path] = DEFAULT_DOC_PATHS
    max_bytes_per_file: int = 2048

    def load(self) -> List[DocumentationSnippet]:
        """Read configured doc files (best-effort) and return excerpts."""

        snippets: List[DocumentationSnippet] = []
        for rel_path in self.doc_paths:
            path = (self.repo_root / rel_path).resolve()
            try:
                data = path.read_text(encoding="utf-8")
            except OSError:
                continue

            excerpt = data[: self.max_bytes_per_file]
            snippets.append(DocumentationSnippet(source=path.name, excerpt=excerpt))
        return snippets


@dataclass
class CommandExecutionLog:
    """Captures a command issued by Ember along with its textual output."""

    command: str
    output: str


@dataclass
class LlamaPlan:
    """Action plan returned by llama.cpp."""

    response: str
    commands: List[str] = field(default_factory=list)


class LlamaInvocationError(RuntimeError):
    """Raised when llama.cpp cannot be executed."""


@dataclass
class LlamaSession:
    """
    Drives llama.cpp through its CLI binary.

    The session builds a context-rich prompt (docs + command history) and
    expects llama.cpp to optionally emit command hints inside [[COMMAND: ...]].
    """

    binary_path: Path = field(default_factory=_default_llama_bin)
    model_path: Path = field(default_factory=_default_model_path)
    max_tokens: int = int(os.environ.get("LLAMA_CPP_MAX_TOKENS", "128"))
    temperature: float = float(os.environ.get("LLAMA_CPP_TEMPERATURE", "0.2"))
    top_p: float = float(os.environ.get("LLAMA_CPP_TOP_P", "0.95"))
    timeout_sec: float = float(os.environ.get("LLAMA_CPP_TIMEOUT", "120"))
    command_history: List[CommandExecutionLog] = field(default_factory=list)
    _doc_snippets: List[DocumentationSnippet] = field(default_factory=list)

    def prime_with_docs(self, snippets: Iterable[DocumentationSnippet]) -> None:
        """Store documentation slices so we can reference them in responses."""

        self._doc_snippets = list(snippets)

    def record_execution(self, log: CommandExecutionLog) -> None:
        """Append a command result to the rolling history."""

        self.command_history.append(log)
        if len(self.command_history) > 10:
            self.command_history[:] = self.command_history[-10:]

    def plan(self, user_prompt: str) -> LlamaPlan:
        """Generate a conversational reply plus a list of commands to run."""

        prompt = self._compose_prompt(user_prompt)
        logger.info("Planning response for prompt: %s", user_prompt[:128])
        try:
            raw_output = self._run_llama(prompt)
        except LlamaInvocationError as exc:
            return LlamaPlan(response=f"[llama.cpp error] {exc}", commands=[])

        commands = self._extract_commands(raw_output)
        response = self._strip_command_markers(raw_output).strip()
        if commands:
            logger.info("llama suggested commands: %s", commands)
        return LlamaPlan(response=response, commands=commands)

    def _compose_prompt(self, user_prompt: str) -> str:
        """Render the full prompt fed into llama.cpp."""

        doc_text = "\n\n".join(
            f"{snippet.source}:\n{snippet.excerpt}"
            for snippet in self._doc_snippets
        ) or "Documentation unavailable."

        history_text = "\n\n".join(
            f"Command: {entry.command}\nOutput: {entry.output}"
            for entry in self.command_history[-5:]
        ) or "No commands executed yet."

        return dedent(
            f"""
            You are Ember's runtime planner running on a Raspberry Pi.
            Use the documentation and command history to stay grounded.
            Always respond with a short summary for the operator first.
            If an Ember CLI command should run, add it on its own line in the form [[COMMAND: <command>]].

            <documentation>
            {doc_text}
            </documentation>

            <command_history>
            {history_text}
            </command_history>

            <user_prompt>
            {user_prompt}
            </user_prompt>
            """
        ).strip()

    def _run_llama(self, prompt: str) -> str:
        """Invoke llama.cpp and return its stdout."""

        binary = self._detect_binary()
        if binary is None:
            raise LlamaInvocationError(
                f"llama binary not found near {self.binary_path}. Set LLAMA_CPP_BIN."
            )

        model = self._detect_model_path()
        if model is None:
            raise LlamaInvocationError(
                "No model found. Place a .gguf under ./models or set LLAMA_CPP_MODEL."
            )

        logger.info(
            "Invoking llama: bin=%s model=%s max_tokens=%s temp=%s top_p=%s",
            binary,
            model,
            self.max_tokens,
            self.temperature,
            self.top_p,
        )

        cmd = [
            str(binary),
            "-m",
            str(model),
            "-n",
            str(self.max_tokens),
            "--temp",
            str(self.temperature),
            "--top-p",
            str(self.top_p),
            "-p",
            prompt,
        ]

        try:
            completed = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except subprocess.TimeoutExpired:
            raise LlamaInvocationError(
                f"llama timed out after {self.timeout_sec} seconds – reduce "
                "LLAMA_CPP_MAX_TOKENS or LLAMA_CPP_TIMEOUT."
            ) from None
        except (subprocess.CalledProcessError, OSError) as exc:
            raise LlamaInvocationError(str(exc)) from exc

        output = completed.stdout.strip()
        logger.info("llama completed (chars=%s)", len(output))
        return output

    def _detect_binary(self) -> Path | None:
        """Resolve the llama binary path, falling back to common locations."""

        env_override = os.environ.get("LLAMA_CPP_BIN")
        candidates = [
            self.binary_path,
            Path(env_override).expanduser() if env_override else None,
            Path("/opt/llama.cpp/build/bin/llama-cli"),
            Path("/opt/llama.cpp/main"),
        ]

        for candidate in candidates:
            if candidate and str(candidate).strip() and candidate.exists():
                return candidate

        which = shutil.which("llama-cli")
        if which:
            return Path(which)

        return None

    def _detect_model_path(self) -> Path | None:
        """Resolve the model path, preferring env vars then local models directory."""

        candidates: List[Path] = []
        env_value = os.environ.get("LLAMA_CPP_MODEL")
        if env_value:
            candidates.append(Path(env_value).expanduser())
        candidates.append(self.model_path)

        model_dirs: List[Path] = [
            Path.cwd() / "models",
            Path("/srv/ember/models"),
            Path("/opt/ember-app/models"),
            Path("/opt/llama.cpp/models"),
        ]

        env_model_dir = os.environ.get("LLAMA_CPP_MODEL_DIR")
        if env_model_dir:
            model_dirs.insert(0, Path(env_model_dir).expanduser())

        for directory in model_dirs:
            if directory and directory.exists():
                ggufs = sorted(directory.glob("*.gguf"))
                bins = sorted(directory.glob("*.bin"))
                for listing in (ggufs, bins):
                    if listing:
                        candidates.extend(listing)
                        break

        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            resolved = candidate.expanduser()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            if resolved.exists():
                return resolved
        return None

    @staticmethod
    def _extract_commands(output: str) -> List[str]:
        """Pull [[COMMAND: ...]] entries out of llama.cpp text."""

        return [match.group(1).strip() for match in COMMAND_PATTERN.finditer(output)]

    @staticmethod
    def _strip_command_markers(output: str) -> str:
        """Remove [[COMMAND: ...]] markers from the text shown to the user."""

        return COMMAND_PATTERN.sub("", output)
