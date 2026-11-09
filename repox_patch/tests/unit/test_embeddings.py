import sys
from types import ModuleType

import pytest

from repox.embeddings.code_rank import MODEL_NAME, QUERY_PREFIX, CodeRankEmbedder
from repox.embeddings.service import embed_chunks
from repox.models.chunk import CodeChunk


class FakeProvider:
    model_name = "fake-model"

    def __init__(self, vectors):
        self.vectors = vectors
        self.received_texts = None

    def embed_documents(self, texts):
        self.received_texts = list(texts)
        return self.vectors

    def embed_query(self, query):
        return [1.0, 0.0]


def _chunk():
    return CodeChunk(
        id="chunk:test",
        file_path="src/example.py",
        language="python",
        kind="function",
        symbol_id="function:src/example.py:calculate",
        symbol_name="calculate",
        start_line=1,
        end_line=2,
        content="def calculate():\n    return 42",
        parent_symbol_id="file:src/example.py",
    )


def test_embed_chunks_attaches_vectors_and_model_metadata():
    chunk = _chunk()
    provider = FakeProvider([[0.25, 0.75]])
    result = embed_chunks([chunk], provider)

    assert len(result) == 1
    assert result[0].chunk == chunk
    assert result[0].vector == [0.25, 0.75]
    assert result[0].model_name == "fake-model"
    assert "Symbol: calculate" in provider.received_texts[0]


def test_embed_chunks_returns_empty_without_calling_provider():
    provider = FakeProvider([])
    assert embed_chunks([], provider) == []
    assert provider.received_texts is None


def test_embed_chunks_rejects_wrong_vector_count():
    with pytest.raises(ValueError, match="vectors for"):
        embed_chunks([_chunk()], FakeProvider([]))


def test_embed_chunks_rejects_inconsistent_dimensions():
    chunks = [_chunk(), _chunk()]
    provider = FakeProvider([[1.0, 0.0], [1.0, 0.0, 0.0]])
    with pytest.raises(ValueError, match="inconsistent dimensions"):
        embed_chunks(chunks, provider)


def test_embed_chunks_rejects_non_finite_values():
    with pytest.raises(ValueError, match="Non-finite"):
        embed_chunks([_chunk()], FakeProvider([[float("nan")]]))


def test_code_rank_embedder_uses_document_and_query_encoding(monkeypatch):
    class FakeArray(list):
        def tolist(self):
            return list(self)

    class FakeTokenizer:
        def __call__(self, texts, **kwargs):
            return {"input_ids": [text.split() for text in texts]}

    class FakeTransformer:
        tokenizer = FakeTokenizer()

    class FakeModel:
        max_seq_length = 8192

        def __init__(self):
            self.calls = []

        def __getitem__(self, index):
            return FakeTransformer()

        def get_embedding_dimension(self):
            return 3

        def encode(self, inputs, **kwargs):
            self.calls.append((inputs, kwargs))
            if isinstance(inputs, str):
                return FakeArray([1.0, 0.0, 0.0])
            return FakeArray([FakeArray([1.0, 0.0, 0.0]) for _ in inputs])

    fake_model = FakeModel()
    captured = {}

    def fake_sentence_transformer(model_name, **kwargs):
        captured["model_name"] = model_name
        captured["kwargs"] = kwargs
        return fake_model

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = fake_sentence_transformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    embedder = CodeRankEmbedder(device="cpu")
    documents = embedder.embed_documents(["def run(): pass"])
    query = embedder.embed_query("where is run defined?")

    assert captured["model_name"] == MODEL_NAME
    assert captured["kwargs"] == {
        "trust_remote_code": True,
        "device": "cpu",
    }
    assert embedder.dimension == 3
    assert documents == [[1.0, 0.0, 0.0]]
    assert query == [1.0, 0.0, 0.0]
    assert fake_model.calls[0][1]["normalize_embeddings"] is True
    assert fake_model.calls[1][0] == QUERY_PREFIX + "where is run defined?"


def test_code_rank_embedder_rejects_empty_query(monkeypatch):
    class FakeModel:
        max_seq_length = 8192

        def get_embedding_dimension(self):
            return 3

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = lambda *args, **kwargs: FakeModel()
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    embedder = CodeRankEmbedder()
    with pytest.raises(ValueError, match="query must not be empty"):
        embedder.embed_query("   ")


def test_code_rank_embedder_rejects_inputs_over_model_limit(monkeypatch):
    class FakeTokenizer:
        def __call__(self, texts, **kwargs):
            return {"input_ids": [text.split() for text in texts]}

    class FakeTransformer:
        tokenizer = FakeTokenizer()

    class FakeModel:
        max_seq_length = 3

        def __getitem__(self, index):
            return FakeTransformer()

        def get_embedding_dimension(self):
            return 3

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = lambda *args, **kwargs: FakeModel()
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    embedder = CodeRankEmbedder()
    with pytest.raises(ValueError, match="model limit is 3"):
        embedder.embed_documents(["this input contains too many tokens"])
