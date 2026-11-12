import pytest

pytest.importorskip("chromadb")

from repox.analyzers.repository_analyzer import analyze_repository  # noqa: E402
from repox.indexing.indexer import RepositoryIndexer  # noqa: E402
from repox.models.chunk import CodeChunk, EmbeddedChunk  # noqa: E402
from repox.vector_store.chroma import ChromaVectorStore  # noqa: E402


def _embedded(
    chunk_id="chunk:test", content="def run(): pass", model_name="test-model"
):
    chunk = CodeChunk(
        id=chunk_id,
        file_path="src/example.py",
        language="python",
        kind="function",
        symbol_id="function:src/example.py:run",
        symbol_name="run",
        start_line=1,
        end_line=1,
        content=content,
        parent_symbol_id="file:src/example.py",
    )
    return EmbeddedChunk(chunk=chunk, vector=[1.0, 0.0], model_name=model_name)


class _Provider:
    dimension = 2

    def __init__(self, model_name, *, fail=False):
        self.model_name = model_name
        self.fail = fail

    def embed_documents(self, texts):
        if self.fail:
            raise RuntimeError("embedding failed")
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, query):
        return [1.0, 0.0]


def _repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    (root / "example.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    return root


def test_chroma_persists_vectors_and_metadata_across_client_recreation(tmp_path):
    store = ChromaVectorStore(tmp_path / "index", "test_collection")
    item = _embedded()
    store.configure("test-model", 2)
    store.upsert([item], {item.chunk.id: "a" * 64})

    reopened = ChromaVectorStore(tmp_path / "index", "test_collection")
    assert reopened.get_chunk_hashes() == {item.chunk.id: "a" * 64}
    matches = reopened.query([1.0, 0.0], 1)
    assert len(matches) == 1
    assert matches[0].document == item.chunk.content
    assert matches[0].metadata["file_path"] == "src/example.py"


def test_chroma_upsert_replaces_same_id_and_delete_removes_it(tmp_path):
    store = ChromaVectorStore(tmp_path / "index", "test_collection")
    first = _embedded(content="def run(): return 1")
    second = _embedded(content="def run(): return 2")
    store.upsert([first], {first.chunk.id: "a" * 64})
    store.upsert([second], {second.chunk.id: "b" * 64})

    assert store.get_chunk_hashes() == {second.chunk.id: "b" * 64}
    assert store.query([1.0, 0.0], 1)[0].document == second.chunk.content
    store.delete([second.chunk.id])
    assert store.get_chunk_hashes() == {}


def test_chroma_rejects_embedding_model_mismatch(tmp_path):
    store = ChromaVectorStore(tmp_path / "index", "test_collection")
    item = _embedded(model_name="model-a")
    store.upsert([item], {item.chunk.id: "a" * 64})
    with pytest.raises(ValueError, match="embedding model"):
        store.configure("model-b", 2)
    with pytest.raises(ValueError, match="embedding dimension"):
        store.configure("model-a", 3)


def test_chroma_empty_collection_returns_no_matches(tmp_path):
    store = ChromaVectorStore(tmp_path / "index", "empty_collection")
    assert store.query([1.0, 0.0], 5) == []


def test_failed_first_embedding_leaves_empty_collection_unconfigured(tmp_path):
    store = ChromaVectorStore(tmp_path / "index", "test_collection")
    analysis = analyze_repository(_repository(tmp_path))

    with pytest.raises(RuntimeError, match="embedding failed"):
        RepositoryIndexer(store, _Provider("model-a", fail=True)).index(analysis)

    assert store.count == 0
    assert "embedding_model" not in (store._collection.metadata or {})

    report = RepositoryIndexer(store, _Provider("model-b")).index(analysis)
    assert report.embedded_chunks > 0
    assert store._collection.metadata["embedding_model"] == "model-b"


def test_failed_embedding_preserves_existing_chroma_vectors(tmp_path):
    store = ChromaVectorStore(tmp_path / "index", "test_collection")
    item = _embedded(model_name="model-a")
    store.upsert([item], {item.chunk.id: "a" * 64})
    before_hashes = store.get_chunk_hashes()
    before_document = store.query([1.0, 0.0], 1)[0].document

    with pytest.raises(RuntimeError, match="embedding failed"):
        RepositoryIndexer(store, _Provider("model-a", fail=True)).index(
            analyze_repository(_repository(tmp_path))
        )

    assert store.get_chunk_hashes() == before_hashes
    assert store.query([1.0, 0.0], 1)[0].document == before_document
