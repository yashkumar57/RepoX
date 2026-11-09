"""Tests for the high-level repository indexing service."""

from pathlib import Path

from repox.indexing.service import RepositoryIndexingService


class FakeEmbeddingProvider:
    model_name = "test-embedding-model"
    dimension = 3

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, query: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class FakeVectorStore:
    def __init__(self) -> None:
        self.hashes: dict[str, str] = {}
        self.upserted_ids: list[str] = []
        self.deleted_ids: list[str] = []

    def configure(self, model_name: str, dimension: int | None = None) -> None:
        assert model_name == "test-embedding-model"
        assert dimension in (None, 3)

    def get_chunk_hashes(self) -> dict[str, str]:
        return self.hashes.copy()

    def upsert(self, chunks, content_hashes) -> None:
        self.upserted_ids.extend(item.chunk.id for item in chunks)
        self.hashes.update(content_hashes)

    def delete(self, chunk_ids) -> None:
        self.deleted_ids.extend(chunk_ids)
        for chunk_id in chunk_ids:
            self.hashes.pop(chunk_id, None)

    def query(self, vector, limit):
        return []


def test_service_analyzes_repository_and_indexes_semantic_chunks() -> None:
    root = Path(__file__).parent.parent / "fixtures" / "sample_repo"
    store = FakeVectorStore()
    service = RepositoryIndexingService(store, FakeEmbeddingProvider())

    result = service.index(root)

    assert result.analyzed_files == 3
    assert result.relationships >= 0
    assert result.report.total_chunks > 0
    assert result.report.embedded_chunks == result.report.total_chunks
    assert result.report.reused_chunks == 0
    assert result.report.deleted_chunks == 0
    assert len(store.upserted_ids) == result.report.total_chunks
