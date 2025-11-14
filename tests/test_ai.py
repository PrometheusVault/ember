"""Unit tests for Ember's AI helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from ember.ai import (
    CommandExecutionLog,
    DocumentationContext,
    DocumentationSnippet,
    LlamaPlan,
    LlamaSession,
)


class FakeLlama:
    """Minimal llama-cpp stub for tests."""

    def __init__(self, text: str = '{"response":"hello","commands":["status"]}') -> None:
        self._text = text
        self.calls = []

    def create_completion(self, **kwargs):  # pragma: no cover - simple stub
        self.calls.append(kwargs)
        return {"choices": [{"text": self._text}]}


def test_plan_parses_commands(tmp_path: Path):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(
        "Commands: {commands}\nDocs: {documentation}\nHistory: {history}\nUser: {user_prompt}",
        encoding="utf-8",
    )
    session = LlamaSession(
        llama_client=FakeLlama(),
        timeout_sec=5,
        command_history=[CommandExecutionLog(command="/status", output="ok")],
        command_names=["status"],
        prompt_template_path=prompt_file,
    )
    session.prime_with_docs([])

    plan: LlamaPlan = session.plan("hello there")

    assert plan.commands == ["status"]
    assert "hello" in plan.response.lower()


def test_responder_uses_tool_outputs(tmp_path: Path):
    session = LlamaSession(
        llama_client=FakeLlama(text='{"response":"done","commands":[]}'),
        timeout_sec=5,
    )
    session.prime_with_docs([])
    reply = session.respond("who are you?", "status: ok")
    assert reply == "done"


def test_responder_strips_code_fence_json(tmp_path: Path):
    fenced = """```json
{
  "response": "Processed water guidance.",
  "commands": []
}
```"""
    session = LlamaSession(
        llama_client=FakeLlama(text=fenced),
        timeout_sec=5,
    )
    session.prime_with_docs([])
    reply = session.respond("help?", "")
    assert reply == "Processed water guidance."


def test_responder_strips_blockquote_prefix(tmp_path: Path):
    text = """> 

```json
{"response": "Stay hydrated.", "commands": []}
```"""
    session = LlamaSession(llama_client=FakeLlama(text=text), timeout_sec=5)
    session.prime_with_docs([])
    reply = session.respond("ping", "")
    assert reply == "Stay hydrated."


def test_documentation_context_reads_files(tmp_path: Path):
    repo = tmp_path
    (repo / "README.md").write_text("readme", encoding="utf-8")
    (repo / "AGENTS.md").write_text("agents", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "ROADMAP.md").write_text("roadmap", encoding="utf-8")

    ctx = DocumentationContext(
        repo_root=repo,
        doc_paths=(Path("README.md"), Path("AGENTS.md"), Path("docs/ROADMAP.md")),
        max_bytes_per_file=4,
    )
    snippets = ctx.load()

    # Each file should be represented and truncated to max_bytes_per_file
    assert {snippet.source for snippet in snippets} == {
        "README.md",
        "AGENTS.md",
        "ROADMAP.md",
    }
    assert all(len(snippet.excerpt) <= 4 for snippet in snippets)


def test_documentation_context_scans_directories(tmp_path: Path):
    repo = tmp_path
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (docs_dir / "field.md").write_text("field procedures", encoding="utf-8")
    (docs_dir / "checklist.txt").write_text("checklist", encoding="utf-8")
    vault = tmp_path / "vault"
    (vault / "docs").mkdir(parents=True)
    (vault / "docs" / "vault.md").write_text("vault notes", encoding="utf-8")

    ctx = DocumentationContext(
        repo_root=repo,
        vault_dir=vault,
        doc_paths=(),
        doc_dirs=(Path("docs"),),
        vault_doc_dirs=(Path("docs"),),
        max_bytes_per_file=32,
        max_files_per_dir=5,
    )
    snippets = ctx.load()

    assert {snippet.source for snippet in snippets} == {"field.md", "checklist.txt", "vault.md"}


def test_documentation_context_honors_max_files(tmp_path: Path):
    repo = tmp_path
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    for idx in range(3):
        (docs_dir / f"file{idx}.md").write_text(f"doc {idx}", encoding="utf-8")

    ctx = DocumentationContext(
        repo_root=repo,
        doc_paths=(),
        doc_dirs=(Path("docs"),),
        max_files_per_dir=2,
    )
    snippets = ctx.load()

    assert len(snippets) == 2
