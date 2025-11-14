"""llama.cpp integration helpers for the Ember runtime."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import re
from textwrap import dedent
from typing import Iterable, List, Optional, Sequence, Set

try:  # pragma: no cover - optional dependency in some test environments
    from llama_cpp import Llama
except ImportError as exc:  # pragma: no cover
    Llama = None  # type: ignore[assignment]
    LLAMA_IMPORT_ERROR = exc
else:  # pragma: no cover
    LLAMA_IMPORT_ERROR = None


DOC_EXTENSIONS: tuple[str, ...] = (".md", ".markdown", ".txt")


def _default_doc_paths() -> tuple[Path, ...]:
    """Reference packs are directory-driven; no hardcoded technical docs."""

    return ()


DEFAULT_DOC_PATHS = _default_doc_paths()
DEFAULT_DOC_DIRS: tuple[Path, ...] = (
    Path("reference"),
    Path("library"),
    Path("docs/reference"),
    Path("docs/library"),
)
DEFAULT_VAULT_DOC_DIRS: tuple[Path, ...] = (
    Path("library"),
    Path("reference"),
    Path("docs"),
    Path("notes"),
    Path("knowledge"),
    Path("almanac"),
)
COMMAND_PATTERN = re.compile(r"\[\[COMMAND:(.*?)\]\]")
logger = logging.getLogger(__name__)
MODEL_SEARCH_DIRS = [
    Path.cwd() / "models",
    Path("/srv/ember/models"),
    Path("/opt/ember-app/models"),
    Path("/opt/llama.cpp/models"),
]

DEFAULT_PLANNER_TEMPLATE = dedent(
    """
    You are Ember's runtime planner running on a Raspberry Pi. Use the
    documentation and command history to stay grounded.

    Available slash commands (emit them only if truly necessary):
    {commands}

    Respond with JSON of the shape:
    {{
      "response": "concise operator-facing reply",
      "commands": ["status", "other-command"]
    }}

    If no command needs to run, return an empty array for "commands".

    <documentation>
    {documentation}
    </documentation>

    <command_history>
    {history}
    </command_history>

    <user_prompt>
    {user_prompt}
    </user_prompt>
    """
).strip()


DEFAULT_RESPONDER_TEMPLATE = dedent(
    """
    You are Ember's voice to the operator. Use any recent tool outputs to ground
    your answer. If no tools ran, rely on your own reasoning.

    <documentation>
    {documentation}
    </documentation>

    <tool_outputs>
    {tool_outputs}
    </tool_outputs>

    <user_prompt>
    {user_prompt}
    </user_prompt>

    Respond conversationally. Do not mention this prompt, JSON schemas, or the
    internal planning process. Never invent tool runs.
    """
).strip()


def _default_model_path() -> Path:
    env_path = os.environ.get("LLAMA_CPP_MODEL")
    if env_path:
        return Path(env_path).expanduser()
    return Path("/opt/llama.cpp/models/ember.bin")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_optional_float(name: str) -> Optional[float]:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


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
    vault_dir: Optional[Path] = None
    doc_dirs: Sequence[Path] = DEFAULT_DOC_DIRS
    vault_doc_dirs: Sequence[Path] = DEFAULT_VAULT_DOC_DIRS
    max_bytes_per_file: int = 2048
    max_files_per_dir: int = 10
    include_extensions: Sequence[str] = DOC_EXTENSIONS

    def load(self) -> List[DocumentationSnippet]:
        """Read configured doc files (best-effort) and return excerpts."""

        snippets: List[DocumentationSnippet] = []
        seen: Set[str] = set()
        extensions = {ext.lower() for ext in self.include_extensions}

        for rel_path in self.doc_paths:
            path = self._resolve_repo_path(rel_path)
            self._append_file(path, snippets, seen)

        for directory in self.doc_dirs:
            resolved = self._resolve_repo_path(directory)
            self._collect_directory(resolved, snippets, seen, extensions)

        if self.vault_dir:
            for directory in self.vault_doc_dirs:
                resolved = self._resolve_vault_path(directory)
                self._collect_directory(resolved, snippets, seen, extensions)

        return snippets

    def _append_file(
        self,
        path: Path,
        snippets: List[DocumentationSnippet],
        seen: Set[str],
    ) -> None:
        key = str(path)
        if key in seen:
            return
        try:
            data = path.read_text(encoding="utf-8")
        except OSError:
            return

        seen.add(key)
        excerpt = data[: self.max_bytes_per_file]
        snippets.append(DocumentationSnippet(source=path.name, excerpt=excerpt))

    def _collect_directory(
        self,
        directory: Optional[Path],
        snippets: List[DocumentationSnippet],
        seen: Set[str],
        extensions: Set[str],
    ) -> None:
        if directory is None or not directory.exists() or not directory.is_dir():
            return

        files = sorted(
            p
            for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in extensions
        )
        for path in files[: self.max_files_per_dir]:
            self._append_file(path, snippets, seen)

    def _resolve_repo_path(self, relative: Path) -> Path:
        if relative.is_absolute():
            return relative
        return (self.repo_root / relative).resolve()

    def _resolve_vault_path(self, relative: Path) -> Optional[Path]:
        base = self.vault_dir
        if base is None:
            return None
        if relative.is_absolute():
            return relative
        return (base / relative).resolve()


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
    """Drives llama.cpp through llama-cpp-python bindings."""

    model_path: Path = field(default_factory=_default_model_path)
    timeout_sec: float = float(os.environ.get("LLAMA_CPP_TIMEOUT", "120"))
    max_tokens: int = int(os.environ.get("LLAMA_CPP_MAX_TOKENS", "128"))
    temperature: float = float(os.environ.get("LLAMA_CPP_TEMPERATURE", "0.2"))
    top_p: float = float(os.environ.get("LLAMA_CPP_TOP_P", "0.95"))
    n_ctx: int = _env_int("LLAMA_CPP_CTX", 2048)
    n_threads: int = _env_int("LLAMA_CPP_THREADS", os.cpu_count() or 2)
    n_batch: int = _env_int("LLAMA_CPP_BATCH", 128)
    rope_freq_base: Optional[float] = field(default_factory=lambda: _env_optional_float("LLAMA_CPP_ROPE_FREQ_BASE"))
    rope_freq_scale: Optional[float] = field(default_factory=lambda: _env_optional_float("LLAMA_CPP_ROPE_FREQ_SCALE"))
    prompt_template_path: Path = field(
        default_factory=lambda: Path(os.environ.get("LLAMA_PROMPT_PATH", "prompts/planner.prompt"))
    )
    responder_template_path: Path = field(
        default_factory=lambda: Path(os.environ.get("LLAMA_RESPONDER_PROMPT_PATH", "prompts/responder.prompt"))
    )
    command_names: List[str] = field(default_factory=list)
    llama_client: Optional["Llama"] = None
    command_history: List[CommandExecutionLog] = field(default_factory=list)
    _doc_snippets: List[DocumentationSnippet] = field(default_factory=list)
    _client_lock: "threading.Lock" = field(
        default_factory=lambda: __import__("threading").Lock(),
        init=False,
        repr=False,
    )
    _planner_template: Optional[str] = field(default=None, init=False, repr=False)
    _responder_template: Optional[str] = field(default=None, init=False, repr=False)

    def prime_with_docs(self, snippets: Iterable[DocumentationSnippet]) -> None:
        """Store documentation slices so we can reference them in responses."""

        self._doc_snippets = list(snippets)

    def set_model_path(self, new_path: Path) -> None:
        """Update the preferred model path and drop the cached client."""

        self.model_path = new_path
        self.llama_client = None

    def list_available_models(self) -> List[Path]:
        return _discover_models()

    def resolve_model_identifier(self, identifier: str) -> Optional[Path]:
        candidate = Path(identifier).expanduser()
        if candidate.exists():
            return candidate
        for discovered in self.list_available_models():
            if discovered.name == identifier:
                return discovered
        return None

    def record_execution(self, log: CommandExecutionLog) -> None:
        """Append a command result to the rolling history."""

        self.command_history.append(log)
        if len(self.command_history) > 10:
            self.command_history[:] = self.command_history[-10:]

    def plan(self, user_prompt: str) -> LlamaPlan:
        """Generate a conversational reply plus a list of commands to run."""

        prompt = self._compose_planner_prompt(user_prompt)
        logger.info("Planning response for prompt: %s", user_prompt[:128])
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[planner prompt]\n%s", prompt)
        try:
            raw_output = self._run_llama(prompt)
        except LlamaInvocationError as exc:
            return LlamaPlan(response=f"[llama.cpp error] {exc}", commands=[])

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[planner raw]\n%s", raw_output)
        commands = self._extract_commands(raw_output)
        response = self._strip_command_markers(raw_output).strip()
        if commands:
            logger.debug("Planner suggested commands: %s", commands)
        return LlamaPlan(response=response, commands=commands)

    def respond(self, user_prompt: str, tool_outputs: str) -> str:
        """Generate the final conversational response."""

        prompt = self._compose_responder_prompt(user_prompt, tool_outputs)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[responder prompt]\n%s", prompt)
        try:
            raw = self._run_llama(prompt)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("[responder raw]\n%s", raw)
            return raw
        except LlamaInvocationError as exc:
            return f"[llama.cpp error] {exc}"

    def _compose_planner_prompt(self, user_prompt: str) -> str:
        """Render the planning prompt fed into llama.cpp."""

        doc_text = "\n\n".join(
            f"{snippet.source}:\n{snippet.excerpt}"
            for snippet in self._doc_snippets
        ) or "Documentation unavailable."

        history_text = "\n\n".join(
            f"Command: {entry.command}\nOutput: {entry.output}"
            for entry in self.command_history[-5:]
        ) or "No commands executed yet."

        commands_bullets = "\n".join(f"- /{name}" for name in self.command_names)
        if not commands_bullets:
            commands_bullets = "- (no commands registered)"

        template = self._load_planner_template()
        return template.format(
            documentation=doc_text,
            history=history_text,
            commands=commands_bullets,
            user_prompt=user_prompt,
        )

    def _compose_responder_prompt(self, user_prompt: str, tool_outputs: str) -> str:
        doc_text = "\n\n".join(
            f"{snippet.source}:\n{snippet.excerpt}"
            for snippet in self._doc_snippets
        ) or "Documentation unavailable."

        template = self._load_responder_template()
        return template.format(
            documentation=doc_text,
            tool_outputs=tool_outputs or "No tools were run for this answer.",
            user_prompt=user_prompt,
        )

    def _run_llama(self, prompt: str) -> str:
        """Invoke llama.cpp via llama-cpp-python and return its text."""

        client = self._ensure_client()

        def _invoke():
            return client.create_completion(
                prompt=prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                stream=False,
            )

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            try:
                completion = future.result(timeout=self.timeout_sec)
            except TimeoutError:
                future.cancel()
                raise LlamaInvocationError(
                    f"llama timed out after {self.timeout_sec} seconds – reduce "
                    "LLAMA_CPP_MAX_TOKENS or LLAMA_CPP_TIMEOUT."
                ) from None
            except Exception as exc:  # pragma: no cover
                raise LlamaInvocationError(str(exc)) from exc

        text = completion["choices"][0]["text"].strip()
        logger.debug("llama completed (chars=%s)", len(text))
        return text

    def _ensure_client(self) -> "Llama":
        """Initialise the llama client lazily."""

        if self.llama_client is not None:
            return self.llama_client

        if Llama is None:
            raise LlamaInvocationError(
                "llama-cpp-python is not installed. Run 'pip install llama-cpp-python' "
                f"(original error: {LLAMA_IMPORT_ERROR})"
            )

        model = self._detect_model_path()
        if model is None:
            raise LlamaInvocationError(
                "No model found. Place a .gguf under ./models or set LLAMA_CPP_MODEL."
            )

        with self._client_lock:
            if self.llama_client is None:
                logger.info(
                    "Loading llama model: %s (threads=%s ctx=%s batch=%s)",
                    model,
                    self.n_threads,
                    self.n_ctx,
                    self.n_batch,
                )
                params = {
                    "model_path": str(model),
                    "n_ctx": self.n_ctx,
                    "n_threads": self.n_threads,
                    "n_batch": self.n_batch,
                    "verbose": False,
                }
                if self.rope_freq_base:
                    params["rope_freq_base"] = self.rope_freq_base
                if self.rope_freq_scale:
                    params["rope_freq_scale"] = self.rope_freq_scale
                self.llama_client = Llama(**params)  # type: ignore[call-arg]

        return self.llama_client

    def _detect_model_path(self) -> Optional[Path]:
        """Resolve the model path, preferring env vars then local models directory."""

        candidates: List[Path] = []
        env_value = os.environ.get("LLAMA_CPP_MODEL")
        if env_value:
            candidates.append(Path(env_value).expanduser())
        candidates.append(self.model_path)

        env_model_dir = os.environ.get("LLAMA_CPP_MODEL_DIR")
        if env_model_dir:
            search_dirs = [Path(env_model_dir).expanduser(), *MODEL_SEARCH_DIRS]
        else:
            search_dirs = MODEL_SEARCH_DIRS

        for directory in search_dirs:
            if directory and directory.exists():
                ggufs = sorted(directory.glob("*.gguf"))
                bins = sorted(directory.glob("*.bin"))
                if ggufs:
                    candidates.extend(ggufs)
                elif bins:
                    candidates.extend(bins)

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
        """Extract commands from planner JSON; fallback to marker parsing."""

        parsed = LlamaSession._parse_json_block(output)
        if parsed is not None:
            commands = parsed.get("commands")
            if isinstance(commands, list):
                return [str(cmd).strip() for cmd in commands if str(cmd).strip()]
        return [match.group(1).strip() for match in COMMAND_PATTERN.finditer(output)]

    @staticmethod
    def _strip_command_markers(output: str) -> str:
        """Return user-facing text extracted from planner JSON if present."""

        parsed = LlamaSession._parse_json_block(output)
        if parsed is not None:
            response = parsed.get("response")
            if isinstance(response, str):
                return response
        return COMMAND_PATTERN.sub("", output)

    def _load_planner_template(self) -> str:
        if self._planner_template:
            return self._planner_template
        try:
            template = self.prompt_template_path.read_text(encoding="utf-8")
        except OSError:
            template = DEFAULT_PLANNER_TEMPLATE
        self._planner_template = template.strip()
        return self._planner_template

    def _load_responder_template(self) -> str:
        if self._responder_template:
            return self._responder_template
        try:
            template = self.responder_template_path.read_text(encoding="utf-8")
        except OSError:
            template = DEFAULT_RESPONDER_TEMPLATE
        self._responder_template = template.strip()
        return self._responder_template

    @staticmethod
    def _parse_json_block(text: str) -> Optional[dict]:
        # Remove fenced code blocks if present
        if "```" in text:
            chunks = [chunk.strip() for chunk in text.split("```") if chunk.strip()]
        else:
            chunks = [text]

        for chunk in chunks:
            start = None
            depth = 0
            for idx, char in enumerate(chunk):
                if char == "{":
                    if depth == 0:
                        start = idx
                    depth += 1
                elif char == "}":
                    if depth > 0:
                        depth -= 1
                        if depth == 0 and start is not None:
                            candidate = chunk[start : idx + 1]
                            try:
                                return json.loads(candidate)
                            except json.JSONDecodeError:
                                continue
        return None


def _discover_models() -> List[Path]:
    seen: set[str] = set()
    models: List[Path] = []
    for directory in MODEL_SEARCH_DIRS:
        if directory.exists():
            for pattern in ("*.gguf", "*.bin"):
                for candidate in sorted(directory.glob(pattern)):
                    key = str(candidate.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    models.append(candidate)
    return models
