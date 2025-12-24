"""Slash command for managing RAG (Retrieval-Augmented Generation)."""

from __future__ import annotations

from pathlib import Path
from typing import List

from rich.console import Console
from rich.table import Table

from ..slash_commands import (
    SlashCommand,
    SlashCommandContext,
    render_rich,
)


def _handler(context: SlashCommandContext, args: List[str]) -> str:
    """Manage the RAG system."""

    if not args:
        return _show_status(context)

    subcommand = args[0].lower()

    if subcommand == "status":
        return _show_status(context)
    elif subcommand == "index":
        return _run_index(context, args[1:])
    elif subcommand == "search":
        return _run_search(context, args[1:])
    elif subcommand == "clear":
        return _clear_index(context)
    elif subcommand == "help":
        return _show_help()
    else:
        return f"[rag] Unknown subcommand '{subcommand}'. Use /rag help for usage."


def _show_status(context: SlashCommandContext) -> str:
    """Show RAG system status."""
    rag_config = context.config.merged.get("rag", {}) if context.config.merged else {}

    def _render(console: Console) -> None:
        table = Table(title="RAG Status", show_header=False)
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("Enabled", str(rag_config.get("enabled", False)))
        table.add_row("Embedding Model", rag_config.get("embedding_model", "all-MiniLM-L6-v2"))
        table.add_row("Chunk Size", str(rag_config.get("chunk_size", 512)))
        table.add_row("Top K", str(rag_config.get("top_k", 3)))

        db_path = context.config.vault_dir / rag_config.get("db_path", "state/rag.db")
        table.add_row("Database", str(db_path))
        table.add_row("DB Exists", str(db_path.exists()))

        # Try to get document count
        if db_path.exists() and rag_config.get("enabled", False):
            try:
                from ..rag.store import VectorStore
                store = VectorStore(db_path)
                store.initialize()
                count = store.count()
                store.close()
                table.add_row("Documents", str(count))
            except Exception as e:
                table.add_row("Documents", f"(error: {e})")
        else:
            table.add_row("Documents", "-")

        # Index directories
        index_dirs = rag_config.get("index_dirs", ["library", "reference", "docs"])
        table.add_row("Index Dirs", ", ".join(index_dirs))

        console.print(table)

    return render_rich(_render)


def _run_index(context: SlashCommandContext, args: List[str]) -> str:
    """Run indexing on specified directories or all configured dirs."""
    rag_config = context.config.merged.get("rag", {}) if context.config.merged else {}

    if not rag_config.get("enabled", False):
        return "[rag] RAG is disabled. Enable it in configuration first."

    try:
        from ..rag.embeddings import get_embedding_model
        from ..rag.indexer import RAGIndexer, ChunkConfig
        from ..rag.store import VectorStore

        # Determine directories to index
        if args:
            directories = [context.config.vault_dir / d for d in args]
        else:
            index_dirs = rag_config.get("index_dirs", ["library", "reference", "docs"])
            directories = [context.config.vault_dir / d for d in index_dirs]

        # Initialize components
        db_path = context.config.vault_dir / rag_config.get("db_path", "state/rag.db")
        store = VectorStore(db_path)
        store.initialize()

        embedding_model = get_embedding_model(
            rag_config.get("embedding_model", "all-MiniLM-L6-v2")
        )
        chunk_config = ChunkConfig(
            chunk_size=int(rag_config.get("chunk_size", 512)),
            chunk_overlap=int(rag_config.get("chunk_overlap", 50)),
        )

        indexer = RAGIndexer(
            store=store,
            embedding_model=embedding_model,
            chunk_config=chunk_config,
        )

        # Index directories
        total_files = 0
        total_chunks = 0

        for directory in directories:
            if directory.exists():
                stats = indexer.index_directory(directory)
                total_files += stats.files_processed
                total_chunks += stats.chunks_created

        store.close()

        return f"[rag] Indexed {total_files} files, {total_chunks} chunks"

    except Exception as e:
        return f"[rag] Indexing failed: {e}"


def _run_search(context: SlashCommandContext, args: List[str]) -> str:
    """Search the RAG index."""
    if not args:
        return "[rag] Usage: /rag search <query>"

    rag_config = context.config.merged.get("rag", {}) if context.config.merged else {}

    if not rag_config.get("enabled", False):
        return "[rag] RAG is disabled. Enable it in configuration first."

    query = " ".join(args)

    try:
        from ..rag.retriever import create_rag_retriever, RAGSettings

        settings = RAGSettings.from_bundle(context.config)
        retriever = create_rag_retriever(context.config.vault_dir, settings)

        if not retriever:
            return "[rag] Failed to initialize retriever"

        results = retriever.query(query, top_k=settings.top_k)

        if not results:
            return f"[rag] No results found for: {query}"

        def _render(console: Console) -> None:
            console.print(f"[bold]Search results for:[/bold] {query}\n")

            for i, result in enumerate(results, 1):
                source = Path(result.document.source).name
                score = result.score
                content = result.document.content[:200]
                if len(result.document.content) > 200:
                    content += "..."

                console.print(f"[cyan]{i}. {source}[/cyan] (score: {score:.2f})")
                console.print(f"   {content}")
                console.print()

        return render_rich(_render)

    except Exception as e:
        return f"[rag] Search failed: {e}"


def _clear_index(context: SlashCommandContext) -> str:
    """Clear the RAG index."""
    rag_config = context.config.merged.get("rag", {}) if context.config.merged else {}

    try:
        from ..rag.store import VectorStore

        db_path = context.config.vault_dir / rag_config.get("db_path", "state/rag.db")

        if not db_path.exists():
            return "[rag] Index does not exist"

        store = VectorStore(db_path)
        store.initialize()
        count = store.count()
        store.clear()
        store.close()

        return f"[rag] Cleared {count} documents from index"

    except Exception as e:
        return f"[rag] Clear failed: {e}"


def _show_help() -> str:
    """Show RAG command help."""
    return """[rag] Usage:
  /rag              Show RAG status
  /rag status       Show RAG status
  /rag index [DIR]  Index documents (default: all configured dirs)
  /rag search QUERY Search the index
  /rag clear        Clear all indexed documents
  /rag help         Show this help

Configuration (in vault config):
  rag:
    enabled: true
    embedding_model: all-MiniLM-L6-v2
    chunk_size: 512
    chunk_overlap: 50
    top_k: 3
    db_path: state/rag.db
    index_dirs:
      - library
      - reference
      - docs"""


COMMAND = SlashCommand(
    name="rag",
    description="Manage RAG (Retrieval-Augmented Generation). Usage: /rag [status|index|search|clear]",
    handler=_handler,
    allow_in_planner=False,
)
