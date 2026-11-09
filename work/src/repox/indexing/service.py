"""High-level deterministic analysis and semantic indexing orchestration."""

from dataclasses import dataclass
from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository
from repox.embeddings.base import EmbeddingProvider
from repox.indexing.indexer import IndexingReport, RepositoryIndexer
from repox.vector_store.base import VectorStore


@dataclass(frozen=True, slots=True)
class RepositoryIndexResult:
    """Indexing report plus deterministic repository analysis counts."""

    report: IndexingReport
    analyzed_files: int
    relationships: int


class RepositoryIndexingService:
    """Analyze a checkout and synchronize its semantic vector index."""

    def __init__(self, store: VectorStore, provider: EmbeddingProvider) -> None:
        self.store = store
        self.provider = provider

    def index(self, repository_root: str | Path) -> RepositoryIndexResult:
        """Run deterministic analysis followed by incremental semantic indexing."""
        analysis = analyze_repository(repository_root)
        report = RepositoryIndexer(self.store, self.provider).index(analysis)
        return RepositoryIndexResult(
            report=report,
            analyzed_files=len(analysis.files),
            relationships=len(analysis.relationships),
        )
