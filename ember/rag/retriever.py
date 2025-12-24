"""RAG retriever for querying the vector store."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .embeddings import EmbeddingModel, get_embedding_model
from .store import Document, VectorStore

logger = logging.getLogger("ember.rag.retriever")


@dataclass
class RetrievalResult:
    """Result from a retrieval query."""

    document: Document
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.document.content,
            "source": self.document.source,
            "score": self.score,
            "metadata": self.document.metadata,
        }


class RAGRetriever:
    """Retrieves relevant documents for queries using semantic search."""

    def __init__(
        self,
        store: VectorStore,
        embedding_model: Optional[EmbeddingModel] = None,
        default_top_k: int = 3,
        score_threshold: float = 0.3,
    ):
        self.store = store
        self.embedding_model = embedding_model or get_embedding_model()
        self.default_top_k = default_top_k
        self.score_threshold = score_threshold

    def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        source_filter: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """Query for relevant documents.

        Args:
            query_text: The query to search for
            top_k: Number of results to return (default: default_top_k)
            source_filter: Optional filter for document sources

        Returns:
            List of RetrievalResult sorted by relevance
        """
        if not query_text.strip():
            return []

        k = top_k or self.default_top_k

        # Generate query embedding
        query_embedding = self.embedding_model.embed(query_text)

        # Search the store
        results = self.store.search(
            query_embedding=query_embedding,
            top_k=k,
            source_filter=source_filter,
        )

        # Filter by score threshold and convert to results
        retrieval_results = []
        for doc, score in results:
            if score >= self.score_threshold:
                retrieval_results.append(RetrievalResult(document=doc, score=score))

        logger.debug(
            "Query '%s' returned %d results (threshold=%.2f)",
            query_text[:50],
            len(retrieval_results),
            self.score_threshold,
        )

        return retrieval_results

    def get_context_for_prompt(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        max_chars: int = 4000,
    ) -> str:
        """Get formatted context string for including in LLM prompts.

        Args:
            query_text: The query to search for
            top_k: Number of results to consider
            max_chars: Maximum characters to include in context

        Returns:
            Formatted context string with relevant document excerpts
        """
        results = self.query(query_text, top_k=top_k)

        if not results:
            return ""

        context_parts = []
        total_chars = 0

        for result in results:
            content = result.document.content
            source = Path(result.document.source).name

            # Check if we have room for this content
            entry = f"[{source}] (relevance: {result.score:.2f})\n{content}"
            entry_len = len(entry)

            if total_chars + entry_len > max_chars:
                # Truncate content to fit
                remaining = max_chars - total_chars - 100  # Leave room for header
                if remaining > 100:
                    truncated = content[:remaining] + "..."
                    entry = f"[{source}] (relevance: {result.score:.2f})\n{truncated}"
                    context_parts.append(entry)
                break

            context_parts.append(entry)
            total_chars += entry_len + 2  # +2 for \n\n

        return "\n\n".join(context_parts)


@dataclass
class RAGSettings:
    """RAG configuration from bundle."""

    enabled: bool = False
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 3
    db_path: str = "state/rag.db"
    index_dirs: List[str] = None

    def __post_init__(self):
        if self.index_dirs is None:
            self.index_dirs = ["library", "reference", "docs"]

    @classmethod
    def from_bundle(cls, bundle) -> "RAGSettings":
        """Create settings from ConfigurationBundle."""
        raw = bundle.merged.get("rag", {}) if bundle.merged else {}

        return cls(
            enabled=bool(raw.get("enabled", False)),
            embedding_model=raw.get("embedding_model", "all-MiniLM-L6-v2"),
            chunk_size=int(raw.get("chunk_size", 512)),
            chunk_overlap=int(raw.get("chunk_overlap", 50)),
            top_k=int(raw.get("top_k", 3)),
            db_path=raw.get("db_path", "state/rag.db"),
            index_dirs=raw.get("index_dirs", ["library", "reference", "docs"]),
        )


def create_rag_retriever(vault_dir: Path, settings: RAGSettings) -> Optional[RAGRetriever]:
    """Create a RAG retriever with the given settings.

    Returns None if RAG is disabled or initialization fails.
    """
    if not settings.enabled:
        return None

    try:
        from .embeddings import get_embedding_model
        from .store import VectorStore

        # Initialize store
        db_path = vault_dir / settings.db_path
        store = VectorStore(db_path)
        store.initialize()

        # Create embedding model
        embedding_model = get_embedding_model(settings.embedding_model)

        # Create retriever
        retriever = RAGRetriever(
            store=store,
            embedding_model=embedding_model,
            default_top_k=settings.top_k,
        )

        logger.info("RAG retriever initialized (db=%s, docs=%d)", db_path, store.count())
        return retriever

    except Exception as e:
        logger.error("Failed to initialize RAG retriever: %s", e)
        return None


__all__ = [
    "RAGRetriever",
    "RetrievalResult",
    "RAGSettings",
    "create_rag_retriever",
]
