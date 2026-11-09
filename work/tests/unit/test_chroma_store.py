import pytest

pytest.importorskip("chromadb")

from repox.models.chunk import CodeChunk, EmbeddedChunk  # noqa: E402
from repox.vector_store.chroma import ChromaVectorStore  # noqa: E402


def _embedded(chunk_id="chunk:test", content="def run(): pass"):
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
    return EmbeddedChunk(chunk=chunk, vector=[1.0, 0.0], model_name="test-model")


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
    store.configure("model-a", 2)
    with pytest.raises(ValueError, match="embedding model"):
        store.configure("model-b", 2)


def test_chroma_empty_collection_returns_no_matches(tmp_path):
    store = ChromaVectorStore(tmp_path / "index", "empty_collection")
    assert store.query([1.0, 0.0], 5) == []
