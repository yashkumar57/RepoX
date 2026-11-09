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

    def __init__(self, store: VectorStore, provider: EmbeddingProvider) -> None:
        self.store = store
        self.provider = provider

    def index(self, analysis: RepositoryAnalysis) -> IndexingReport:
        """Index all current chunks, reusing unchanged vectors and pruning stale IDs.

        Embeddings are generated before stale records are deleted. If chunking or
        embedding fails, the existing index is left intact.
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

        embedded = embed_chunks(changed_chunks, self.provider)
        if embedded:
            actual_dimension = len(embedded[0].vector)
            self.store.configure(self.provider.model_name, actual_dimension)
            self.store.upsert(embedded, hashes)
        self.store.delete(stale_ids)

        return IndexingReport(
            total_chunks=len(chunks),
            embedded_chunks=len(embedded),
            reused_chunks=len(chunks) - len(embedded),
            deleted_chunks=len(stale_ids),
        )
