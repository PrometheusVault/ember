"""Vector store implementation for RAG using SQLite with optional VSS extension."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math

logger = logging.getLogger("ember.rag.store")


@dataclass
class Document:
    """Represents a document chunk with its embedding."""

    id: str
    content: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "metadata": self.metadata,
        }


class VectorStore:
    """SQLite-based vector store with cosine similarity search.

    Uses pure Python for vector operations when sqlite-vss is not available.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._has_vss = False

    def initialize(self) -> None:
        """Initialize the database and tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # Try to load sqlite-vss extension
        try:
            self._conn.enable_load_extension(True)
            self._conn.load_extension("vss0")
            self._has_vss = True
            logger.info("sqlite-vss extension loaded")
        except Exception:
            self._has_vss = False
            logger.info("sqlite-vss not available, using pure Python similarity search")

        self._create_tables()

    def _create_tables(self) -> None:
        """Create necessary database tables."""
        cursor = self._conn.cursor()

        # Main documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                metadata TEXT,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for source lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source)
        """)

        self._conn.commit()

    def add_document(self, doc: Document) -> None:
        """Add a document to the store."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.cursor()

        # Serialize embedding as JSON blob
        embedding_blob = json.dumps(doc.embedding) if doc.embedding else None

        cursor.execute("""
            INSERT OR REPLACE INTO documents (id, content, source, metadata, embedding)
            VALUES (?, ?, ?, ?, ?)
        """, (
            doc.id,
            doc.content,
            doc.source,
            json.dumps(doc.metadata),
            embedding_blob,
        ))

        self._conn.commit()

    def add_documents(self, docs: List[Document]) -> None:
        """Add multiple documents efficiently."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.cursor()

        data = [
            (
                doc.id,
                doc.content,
                doc.source,
                json.dumps(doc.metadata),
                json.dumps(doc.embedding) if doc.embedding else None,
            )
            for doc in docs
        ]

        cursor.executemany("""
            INSERT OR REPLACE INTO documents (id, content, source, metadata, embedding)
            VALUES (?, ?, ?, ?, ?)
        """, data)

        self._conn.commit()
        logger.info("Added %d documents to store", len(docs))

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        source_filter: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
        """Search for similar documents using cosine similarity.

        Returns list of (document, similarity_score) tuples.
        """
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.cursor()

        # Build query
        if source_filter:
            cursor.execute(
                "SELECT id, content, source, metadata, embedding FROM documents WHERE source LIKE ?",
                (f"%{source_filter}%",)
            )
        else:
            cursor.execute(
                "SELECT id, content, source, metadata, embedding FROM documents WHERE embedding IS NOT NULL"
            )

        results: List[Tuple[Document, float]] = []

        for row in cursor.fetchall():
            if not row["embedding"]:
                continue

            doc_embedding = json.loads(row["embedding"])
            similarity = self._cosine_similarity(query_embedding, doc_embedding)

            doc = Document(
                id=row["id"],
                content=row["content"],
                source=row["source"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                embedding=doc_embedding,
            )

            results.append((doc, similarity))

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT id, content, source, metadata, embedding FROM documents WHERE id = ?",
            (doc_id,)
        )

        row = cursor.fetchone()
        if not row:
            return None

        return Document(
            id=row["id"],
            content=row["content"],
            source=row["source"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
        )

    def delete_by_source(self, source: str) -> int:
        """Delete all documents from a specific source."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM documents WHERE source = ?", (source,))
        self._conn.commit()

        return cursor.rowcount

    def clear(self) -> None:
        """Clear all documents from the store."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM documents")
        self._conn.commit()
        logger.info("Cleared all documents from store")

    def count(self) -> int:
        """Get total document count."""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


__all__ = ["VectorStore", "Document"]
