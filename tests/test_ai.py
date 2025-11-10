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


def test_documentation_context_reads_files(tmp_path: Path):
    repo = tmp_path
    (repo / "README.md").write_text("readme", encoding="utf-8")
    (repo / "AGENTS.md").write_text("agents", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "ROADMAP.md").write_text("roadmap", encoding="utf-8")

    ctx = DocumentationContext(repo_root=repo, max_bytes_per_file=4)
    snippets = ctx.load()

    # Each file should be represented and truncated to max_bytes_per_file
    assert {snippet.source for snippet in snippets} == {
        "README.md",
        "AGENTS.md",
        "ROADMAP.md",
    }
    assert all(len(snippet.excerpt) <= 4 for snippet in snippets)
