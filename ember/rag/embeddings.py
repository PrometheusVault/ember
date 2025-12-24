"""Embedding generation for RAG."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger("ember.rag.embeddings")


class EmbeddingModel(ABC):
    """Abstract base class for embedding models."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class SentenceTransformerEmbedding(EmbeddingModel):
    """Embedding model using sentence-transformers library."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._dimension: Optional[int] = None

    def _ensure_model(self) -> None:
        """Lazy load the model."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info("Embedding model loaded (dim=%d)", self._dimension)
        except ImportError as e:
            raise RuntimeError(
                f"sentence-transformers is not installed. "
                f"Run 'pip install sentence-transformers' to enable RAG. "
                f"(Error: {e})"
            )

    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        self._ensure_model()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        self._ensure_model()
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        self._ensure_model()
        return self._dimension or 384  # Default for MiniLM


class SimpleHashEmbedding(EmbeddingModel):
    """Simple hash-based embedding for testing when sentence-transformers is unavailable.

    This is NOT suitable for production - only for testing/fallback.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    def embed(self, text: str) -> List[float]:
        """Generate a simple hash-based embedding."""
        import hashlib

        # Create a deterministic but pseudo-random embedding from text hash
        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Expand hash to fill dimension
        embedding = []
        for i in range(self._dimension):
            byte_idx = i % len(hash_bytes)
            value = (hash_bytes[byte_idx] + i) / 255.0 - 0.5
            embedding.append(value)

        # Normalize
        norm = sum(v * v for v in embedding) ** 0.5
        if norm > 0:
            embedding = [v / norm for v in embedding]

        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(text) for text in texts]

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension


def get_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingModel:
    """Get an embedding model instance.

    Tries to use sentence-transformers, falls back to simple hash if unavailable.
    """
    try:
        return SentenceTransformerEmbedding(model_name)
    except RuntimeError:
        logger.warning(
            "sentence-transformers not available, using fallback hash embeddings. "
            "Install with: pip install sentence-transformers"
        )
        return SimpleHashEmbedding()


__all__ = [
    "EmbeddingModel",
    "SentenceTransformerEmbedding",
    "SimpleHashEmbedding",
    "get_embedding_model",
]
