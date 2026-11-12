from pathlib import Path

import pytest

from repox.analyzers.repository_analyzer import analyze_repository
from repox.chunking.semantic_chunker import chunk_repository
from repox.models.search import SearchResult
from repox.query.retrieval import RepositoryRetrievalService


class FakeSemanticSearch:
    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    def search(self, query, top_k=5):
        self.calls.append((query, top_k))
        return self.matches[:top_k]


def _analysis(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "helpers.py").write_text(
        "def normalize(value):\n    return value.strip()\n",
        encoding="utf-8",
    )
    (root / "main.py").write_text(
        "from helpers import normalize\n\n"
        "def handle(value):\n    return normalize(value)\n\n"
        "def endpoint(value):\n    return handle(value)\n",
        encoding="utf-8",
    )
    return analyze_repository(root)


def _semantic_match(analysis, symbol_id, score=0.9):
    chunk = next(
        chunk for chunk in chunk_repository(analysis) if chunk.symbol_id == symbol_id
    )
    return SearchResult(chunk=chunk, score=score, distance=1.0 - score)


def test_retrieval_returns_semantic_match_and_call_graph_context(tmp_path):
    analysis = _analysis(tmp_path)
    match = _semantic_match(analysis, "function:main.py:handle")
    search = FakeSemanticSearch([match])

    response = RepositoryRetrievalService(analysis, search).retrieve(
        "handle request", top_k=3
    )

    assert response.semantic_match_count == 1
    assert response.structural_context_count >= 2
    assert response.results[0].chunk.id == match.chunk.id
    assert response.results[0].semantic_score == pytest.approx(0.9)

    context = {
        item.chunk.symbol_id: item
        for item in response.results
        if not item.is_semantic_match
    }
    assert "function:main.py:endpoint" in context
    assert "function:helpers.py:normalize" in context
    assert "caller" in context["function:main.py:endpoint"].relationships
    assert "callee" in context["function:helpers.py:normalize"].relationships


def test_retrieval_includes_parent_source_and_import_relationship(tmp_path):
    analysis = _analysis(tmp_path)
    match = _semantic_match(analysis, "function:main.py:handle")
    response = RepositoryRetrievalService(
        analysis, FakeSemanticSearch([match])
    ).retrieve("handle", context_limit=10)

    module_context = [
        item for item in response.results if item.chunk.symbol_id == "file:main.py"
    ]
    assert module_context
    assert any(
        "from helpers import normalize" in item.chunk.content for item in module_context
    )
    assert "parent" in module_context[0].relationships


def test_retrieval_deduplicates_chunks_reached_from_multiple_matches(tmp_path):
    analysis = _analysis(tmp_path)
    first = _semantic_match(analysis, "function:main.py:handle", 0.95)
    second = _semantic_match(analysis, "function:main.py:endpoint", 0.85)
    response = RepositoryRetrievalService(
        analysis, FakeSemanticSearch([first, second])
    ).retrieve("request flow", top_k=2, context_limit=20)

    ids = [item.chunk.id for item in response.results]
    assert len(ids) == len(set(ids))
    assert response.semantic_match_count == 2
    by_symbol = {item.chunk.symbol_id: item for item in response.results}
    assert "callee" in by_symbol["function:main.py:handle"].relationships
    assert "caller" in by_symbol["function:main.py:endpoint"].relationships


def test_retrieval_context_limit_is_respected(tmp_path):
    analysis = _analysis(tmp_path)
    match = _semantic_match(analysis, "function:main.py:handle")
    response = RepositoryRetrievalService(
        analysis, FakeSemanticSearch([match])
    ).retrieve("handle", context_limit=1)

    assert response.semantic_match_count == 1
    assert response.structural_context_count <= 1
    assert len(response.results) <= 2


def test_retrieval_rejects_negative_context_limit(tmp_path):
    analysis = _analysis(tmp_path)
    service = RepositoryRetrievalService(analysis, FakeSemanticSearch([]))

    with pytest.raises(ValueError, match="context_limit"):
        service.retrieve("query", context_limit=-1)


def test_retrieval_returns_empty_response_when_semantic_search_has_no_matches(
    tmp_path,
):
    analysis = _analysis(tmp_path)
    service = RepositoryRetrievalService(analysis, FakeSemanticSearch([]))

    response = service.retrieve("unmatched query")

    assert response.results == ()
    assert response.semantic_match_count == 0
    assert response.structural_context_count == 0


def test_retrieval_adds_context_for_a_duplicate_definition(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "example.py").write_text(
        "class Duplicate:\n"
        "    def run(self):\n"
        "        return 1\n\n"
        "class Duplicate:\n"
        "    def run(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )
    analysis = analyze_repository(root)
    method = next(
        chunk
        for chunk in chunk_repository(analysis)
        if chunk.kind == "function" and chunk.start_line == 6
    )
    response = RepositoryRetrievalService(
        analysis, FakeSemanticSearch([SearchResult(method, score=0.9, distance=0.1)])
    ).retrieve("second duplicate", context_limit=5)

    parent = next(item for item in response.results if item.chunk.id != method.id)
    assert parent.chunk.symbol_id == method.parent_symbol_id
    assert "parent" in parent.relationships
