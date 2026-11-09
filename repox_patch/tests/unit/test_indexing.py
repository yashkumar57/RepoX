from pathlib import Path

import pytest

from repox.analyzers.repository_analyzer import analyze_repository
from repox.indexing.indexer import RepositoryIndexer
from repox.indexing.search import SemanticSearchService
from repox.vector_store.base import StoredVector


class FakeProvider:
    model_name = "test-model"
    dimension = 2

    def __init__(self):
        self.document_calls = []
        self.query_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(list(texts))
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, query):
        self.query_calls.append(query)
        return [1.0, 0.0]


class FakeStore:
    def __init__(self):
        self.hashes = {}
        self.chunks = {}
        self.model_name = None
        self.dimension = None
        self.query_matches = []
        self.deleted = []

    def configure(self, model_name, dimension=None):
        if self.model_name is not None and self.model_name != model_name:
            raise ValueError("model mismatch")
        if (
            dimension is not None
            and self.dimension is not None
            and self.dimension != dimension
        ):
            raise ValueError("dimension mismatch")
        self.model_name = model_name
        if dimension is not None:
            self.dimension = dimension

    def get_chunk_hashes(self):
        return dict(self.hashes)

    def upsert(self, chunks, content_hashes):
        for item in chunks:
            self.chunks[item.chunk.id] = item
            self.hashes[item.chunk.id] = content_hashes[item.chunk.id]

    def delete(self, chunk_ids):
        self.deleted.extend(chunk_ids)
        for chunk_id in chunk_ids:
            self.hashes.pop(chunk_id, None)
            self.chunks.pop(chunk_id, None)

    def query(self, vector, limit):
        return self.query_matches[:limit]


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "sample"
    root.mkdir()
    (root / "example.py").write_text(
        "def calculate(value):\n    return value + 1\n", encoding="utf-8"
    )
    return root


def test_indexer_embeds_first_run_and_reuses_unchanged_chunks(tmp_path):
    root = _repository(tmp_path)
    provider = FakeProvider()
    store = FakeStore()
    indexer = RepositoryIndexer(store, provider)

    first = indexer.index(analyze_repository(root))
    assert first.total_chunks > 0
    assert first.embedded_chunks == first.total_chunks
    assert first.reused_chunks == 0
    assert len(provider.document_calls) == 1

    second = indexer.index(analyze_repository(root))
    assert second.embedded_chunks == 0
    assert second.reused_chunks == second.total_chunks
    assert len(provider.document_calls) == 1


def test_indexer_reembeds_changed_content_with_same_chunk_id(tmp_path):
    root = _repository(tmp_path)
    provider = FakeProvider()
    store = FakeStore()
    indexer = RepositoryIndexer(store, provider)
    indexer.index(analyze_repository(root))
    previous_ids = set(store.hashes)

    (root / "example.py").write_text(
        "def calculate(value):\n    return value + 2\n", encoding="utf-8"
    )
    report = indexer.index(analyze_repository(root))

    assert previous_ids == set(store.hashes)
    assert report.embedded_chunks == report.total_chunks
    assert len(provider.document_calls) == 2


def test_indexer_removes_stale_chunks_after_file_deletion(tmp_path):
    root = _repository(tmp_path)
    (root / "other.py").write_text("VALUE = 42\n", encoding="utf-8")
    provider = FakeProvider()
    store = FakeStore()
    indexer = RepositoryIndexer(store, provider)
    indexer.index(analyze_repository(root))
    before = set(store.hashes)

    (root / "other.py").unlink()
    report = indexer.index(analyze_repository(root))

    assert report.deleted_chunks > 0
    assert set(store.hashes) < before
    assert report.total_chunks == len(store.hashes)


def test_search_maps_stored_metadata_to_source_grounded_result():
    provider = FakeProvider()
    store = FakeStore()
    store.query_matches = [
        StoredVector(
            id="chunk:example",
            document="def calculate():\n    return 42",
            metadata={
                "file_path": "src/example.py",
                "language": "python",
                "kind": "function",
                "symbol_id": "function:src/example.py:calculate",
                "symbol_name": "calculate",
                "start_line": 4,
                "end_line": 5,
                "parent_symbol_id": "file:src/example.py",
            },
            distance=0.12,
        )
    ]

    results = SemanticSearchService(store, provider).search("where is calculate?", 3)

    assert len(results) == 1
    assert results[0].chunk.file_path == "src/example.py"
    assert results[0].chunk.start_line == 4
    assert results[0].chunk.content.startswith("def calculate")
    assert results[0].score == pytest.approx(0.88)
    assert provider.query_calls == ["where is calculate?"]


def test_search_rejects_invalid_query_and_top_k():
    service = SemanticSearchService(FakeStore(), FakeProvider())
    with pytest.raises(ValueError, match="query must not be empty"):
        service.search("  ")
    with pytest.raises(ValueError, match="top_k"):
        service.search("calculate", 0)


def test_indexer_rejects_model_change_instead_of_mixing_vectors(tmp_path):
    root = _repository(tmp_path)
    store = FakeStore()
    RepositoryIndexer(store, FakeProvider()).index(analyze_repository(root))

    class OtherProvider(FakeProvider):
        model_name = "other-model"

    with pytest.raises(ValueError, match="model mismatch"):
        RepositoryIndexer(store, OtherProvider()).index(analyze_repository(root))


def test_content_hash_is_stored_for_every_embedded_chunk(tmp_path):
    root = _repository(tmp_path)
    store = FakeStore()
    report = RepositoryIndexer(store, FakeProvider()).index(analyze_repository(root))

    assert report.total_chunks == len(store.hashes)
    assert all(len(value) == 64 for value in store.hashes.values())


def test_indexer_does_not_prune_records_when_repository_scan_has_errors(tmp_path):
    root = _repository(tmp_path)
    store = FakeStore()
    indexer = RepositoryIndexer(store, FakeProvider())
    indexer.index(analyze_repository(root))
    previous = dict(store.hashes)
    (root / "unreadable.py").write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(ValueError, match="scanning failed"):
        indexer.index(analyze_repository(root))

    assert store.hashes == previous
