"""Document indexer for RAG."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .embeddings import EmbeddingModel, get_embedding_model
from .store import Document, VectorStore

logger = logging.getLogger("ember.rag.indexer")

# Supported file extensions for indexing
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".rst"}


@dataclass
class ChunkConfig:
    """Configuration for text chunking."""

    chunk_size: int = 512
    chunk_overlap: int = 50
    min_chunk_size: int = 50


@dataclass
class IndexStats:
    """Statistics from an indexing operation."""

    files_processed: int = 0
    chunks_created: int = 0
    errors: int = 0
    skipped: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "files_processed": self.files_processed,
            "chunks_created": self.chunks_created,
            "errors": self.errors,
            "skipped": self.skipped,
        }


class RAGIndexer:
    """Indexes documents from vault directories into the vector store."""

    def __init__(
        self,
        store: VectorStore,
        embedding_model: Optional[EmbeddingModel] = None,
        chunk_config: Optional[ChunkConfig] = None,
    ):
        self.store = store
        self.embedding_model = embedding_model or get_embedding_model()
        self.chunk_config = chunk_config or ChunkConfig()

    def index_directory(
        self,
        directory: Path,
        extensions: Optional[Sequence[str]] = None,
        recursive: bool = True,
    ) -> IndexStats:
        """Index all supported files in a directory.

        Args:
            directory: Path to directory to index
            extensions: File extensions to include (default: SUPPORTED_EXTENSIONS)
            recursive: Whether to search recursively

        Returns:
            IndexStats with results
        """
        stats = IndexStats()
        exts = set(extensions) if extensions else SUPPORTED_EXTENSIONS

        if not directory.exists():
            logger.warning("Directory does not exist: %s", directory)
            return stats

        # Find all matching files
        if recursive:
            files = [
                f for f in directory.rglob("*")
                if f.is_file() and f.suffix.lower() in exts
            ]
        else:
            files = [
                f for f in directory.iterdir()
                if f.is_file() and f.suffix.lower() in exts
            ]

        logger.info("Found %d files to index in %s", len(files), directory)

        # Process files
        all_documents: List[Document] = []

        for file_path in files:
            try:
                docs = self._process_file(file_path)
                all_documents.extend(docs)
                stats.files_processed += 1
                stats.chunks_created += len(docs)
            except Exception as e:
                logger.error("Error processing %s: %s", file_path, e)
                stats.errors += 1

        # Generate embeddings in batches
        if all_documents:
            self._add_embeddings(all_documents)
            self.store.add_documents(all_documents)

        logger.info(
            "Indexed %d files, %d chunks from %s",
            stats.files_processed,
            stats.chunks_created,
            directory,
        )

        return stats

    def index_file(self, file_path: Path) -> IndexStats:
        """Index a single file.

        Args:
            file_path: Path to file to index

        Returns:
            IndexStats with results
        """
        stats = IndexStats()

        if not file_path.exists():
            logger.warning("File does not exist: %s", file_path)
            return stats

        try:
            docs = self._process_file(file_path)
            if docs:
                self._add_embeddings(docs)
                self.store.add_documents(docs)
                stats.files_processed = 1
                stats.chunks_created = len(docs)
        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e)
            stats.errors = 1

        return stats

    def _process_file(self, file_path: Path) -> List[Document]:
        """Process a file and return document chunks."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            raise RuntimeError(f"Failed to read file: {e}")

        if not content.strip():
            return []

        # Chunk the content
        chunks = self._chunk_text(content)

        # Create documents
        documents = []
        for i, chunk in enumerate(chunks):
            doc_id = self._generate_id(file_path, i)
            doc = Document(
                id=doc_id,
                content=chunk,
                source=str(file_path),
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_name": file_path.name,
                },
            )
            documents.append(doc)

        return documents

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        config = self.chunk_config

        # Clean the text
        text = text.strip()
        if not text:
            return chunks

        # Split by paragraphs first for natural boundaries
        paragraphs = text.split("\n\n")
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_length = len(para)

            # If paragraph alone is larger than chunk size, split it
            if para_length > config.chunk_size:
                # Flush current chunk
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # Split large paragraph into sentences/words
                words = para.split()
                word_chunk = []
                word_length = 0

                for word in words:
                    if word_length + len(word) + 1 > config.chunk_size and word_chunk:
                        chunks.append(" ".join(word_chunk))
                        # Keep overlap
                        overlap_words = int(config.chunk_overlap / 5)  # ~5 chars per word
                        word_chunk = word_chunk[-overlap_words:] if overlap_words > 0 else []
                        word_length = sum(len(w) + 1 for w in word_chunk)

                    word_chunk.append(word)
                    word_length += len(word) + 1

                if word_chunk:
                    if current_chunk:
                        current_chunk.append(" ".join(word_chunk))
                        current_length += word_length
                    else:
                        chunks.append(" ".join(word_chunk))

            elif current_length + para_length > config.chunk_size and current_chunk:
                # Flush current chunk
                chunks.append("\n\n".join(current_chunk))
                # Keep last paragraph for overlap
                current_chunk = [para] if config.chunk_overlap > 0 else []
                current_length = para_length if config.chunk_overlap > 0 else 0

            else:
                current_chunk.append(para)
                current_length += para_length + 2  # +2 for \n\n

        # Don't forget the last chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        # Filter out chunks that are too small
        chunks = [c for c in chunks if len(c) >= config.min_chunk_size]

        return chunks

    def _add_embeddings(self, documents: List[Document]) -> None:
        """Add embeddings to documents in batches."""
        batch_size = 32
        texts = [doc.content for doc in documents]

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_embeddings = self.embedding_model.embed_batch(batch_texts)

            for j, embedding in enumerate(batch_embeddings):
                documents[i + j].embedding = embedding

    def _generate_id(self, file_path: Path, chunk_index: int) -> str:
        """Generate a unique ID for a document chunk."""
        source = f"{file_path}:{chunk_index}"
        return hashlib.sha256(source.encode()).hexdigest()[:16]

    def reindex_all(self, directories: List[Path]) -> IndexStats:
        """Clear the store and reindex all directories."""
        self.store.clear()

        total_stats = IndexStats()
        for directory in directories:
            stats = self.index_directory(directory)
            total_stats.files_processed += stats.files_processed
            total_stats.chunks_created += stats.chunks_created
            total_stats.errors += stats.errors
            total_stats.skipped += stats.skipped

        return total_stats


__all__ = ["RAGIndexer", "ChunkConfig", "IndexStats"]
