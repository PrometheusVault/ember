"""RAG indexing agent for maintaining the vector store."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from ..configuration import ConfigurationBundle

logger = logging.getLogger("ember.agents.rag")


@dataclass
class RAGAgentResult:
    """Result from the RAG indexing agent."""

    status: str  # "ok", "skipped", "error"
    detail: str
    files_indexed: int = 0
    chunks_created: int = 0
    errors: int = 0
    db_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "files_indexed": self.files_indexed,
            "chunks_created": self.chunks_created,
            "errors": self.errors,
            "db_path": self.db_path,
        }


def run_rag_agent(bundle: ConfigurationBundle) -> RAGAgentResult:
    """Index vault documents into the RAG vector store."""

    rag_config = bundle.merged.get("rag", {}) if bundle.merged else {}

    if not rag_config.get("enabled", False):
        detail = "rag.agent disabled via configuration"
        logger.info(detail)
        return RAGAgentResult(status="skipped", detail=detail)

    try:
        from ..rag.embeddings import get_embedding_model
        from ..rag.indexer import RAGIndexer, ChunkConfig
        from ..rag.store import VectorStore

        # Get settings
        db_path = bundle.vault_dir / rag_config.get("db_path", "state/rag.db")
        chunk_size = int(rag_config.get("chunk_size", 512))
        chunk_overlap = int(rag_config.get("chunk_overlap", 50))
        index_dirs = rag_config.get("index_dirs", ["library", "reference", "docs"])
        embedding_model_name = rag_config.get("embedding_model", "all-MiniLM-L6-v2")

        # Initialize components
        store = VectorStore(db_path)
        store.initialize()

        embedding_model = get_embedding_model(embedding_model_name)
        chunk_config = ChunkConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        indexer = RAGIndexer(
            store=store,
            embedding_model=embedding_model,
            chunk_config=chunk_config,
        )

        # Index directories
        total_files = 0
        total_chunks = 0
        total_errors = 0

        for dir_name in index_dirs:
            directory = bundle.vault_dir / dir_name
            if directory.exists():
                stats = indexer.index_directory(directory)
                total_files += stats.files_processed
                total_chunks += stats.chunks_created
                total_errors += stats.errors

        store.close()

        detail = f"indexed {total_files} files, {total_chunks} chunks"
        if total_errors:
            detail += f", {total_errors} errors"

        logger.info("rag.agent completed: %s", detail)

        return RAGAgentResult(
            status="ok" if total_errors == 0 else "partial",
            detail=detail,
            files_indexed=total_files,
            chunks_created=total_chunks,
            errors=total_errors,
            db_path=str(db_path),
        )

    except Exception as e:
        logger.exception("RAG agent failed: %s", e)
        return RAGAgentResult(
            status="error",
            detail=str(e),
        )


__all__ = ["run_rag_agent", "RAGAgentResult"]
