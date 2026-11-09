"""Incremental repository-to-vector-index orchestration."""

from dataclasses import dataclass
from hashlib import sha256

from repox.chunking.semantic_chunker import chunk_repository
from repox.embeddings.base import EmbeddingProvider
from repox.embeddings.service import embed_chunks
from repox.models.analysis import RepositoryAnalysis
from repox.models.chunk import CodeChunk
from repox.vector_store.base import VectorStore


@dataclass(frozen=True)
class IndexingReport:
    """Summary of one full repository synchronization."""

    total_chunks: int
    embedded_chunks: int
    reused_chunks: int
    deleted_chunks: int


def chunk_content_hash(chunk: CodeChunk) -> str:
    """Hash the exact embedding input, including metadata and source code."""
    return sha256(chunk.embedding_text.encode("utf-8")).hexdigest()


class RepositoryIndexer:
    """Synchronize a deterministic repository analysis into a vector store."""

    def __init__(
        self,
        store: VectorStore,
        provider: EmbeddingProvider,
        batch_size: int = 8,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.store = store
        self.provider = provider
        self.batch_size = batch_size

    def index(self, analysis: RepositoryAnalysis) -> IndexingReport:
        """Index all current chunks, reusing unchanged vectors and pruning stale IDs.

        Changed chunks are embedded and persisted in bounded batches to avoid
        retaining every embedding vector in memory. Stale records are deleted
        only after all changed batches have been processed successfully.
        """
        if analysis.scan_errors:
            paths = ", ".join(error.path for error in analysis.scan_errors[:5])
            raise ValueError(
                "Cannot safely synchronize the vector index because repository "
                f"scanning failed for {len(analysis.scan_errors)} file(s): {paths}. "
                "Resolve the scan errors and retry so unreadable files are not "
                "mistakenly treated as deleted files."
            )

        chunks = chunk_repository(analysis)
        hashes = {chunk.id: chunk_content_hash(chunk) for chunk in chunks}
        dimension = getattr(self.provider, "dimension", None)
        self.store.configure(self.provider.model_name, dimension)

        existing = self.store.get_chunk_hashes()
        current_ids = set(hashes)
        stale_ids = sorted(set(existing) - current_ids)
        changed_chunks = [
            chunk for chunk in chunks if existing.get(chunk.id) != hashes[chunk.id]
        ]

        embedded_count = 0
        for start in range(0, len(changed_chunks), self.batch_size):
            batch = changed_chunks[start : start + self.batch_size]
            embedded_batch = embed_chunks(batch, self.provider)
            if not embedded_batch:
                continue
            actual_dimension = len(embedded_batch[0].vector)
            self.store.configure(self.provider.model_name, actual_dimension)
            self.store.upsert(embedded_batch, hashes)
            embedded_count += len(embedded_batch)
            del embedded_batch

        self.store.delete(stale_ids)

        return IndexingReport(
            total_chunks=len(chunks),
            embedded_chunks=embedded_count,
            reused_chunks=len(chunks) - embedded_count,
            deleted_chunks=len(stale_ids),
        )
