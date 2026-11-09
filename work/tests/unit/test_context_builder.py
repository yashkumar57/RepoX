from pathlib import Path

import pytest

from repox.analyzers.repository_analyzer import analyze_repository
from repox.chunking.semantic_chunker import chunk_repository
from repox.context import PromptBuilder, RAGContextBuilder
from repox.models.retrieval import RetrievalResponse, RetrievedChunk


class CharacterCounter:
    """Predictable test counter: one token per character."""

    def count(self, text: str) -> int:
        return len(text)


def _retrieval(tmp_path: Path) -> RetrievalResponse:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "helpers.py").write_text(
        "def normalize(value):\n    return value.strip()\n", encoding="utf-8"
    )
    (root / "main.py").write_text(
        "from helpers import normalize\n\n"
        "def handle(value):\n    return normalize(value)\n\n"
        "def endpoint(value):\n    return handle(value)\n",
        encoding="utf-8",
    )
    analysis = analyze_repository(root)
    chunks = chunk_repository(analysis)
    handle = next(chunk for chunk in chunks if chunk.symbol_name == "handle")
    normalize = next(chunk for chunk in chunks if chunk.symbol_name == "normalize")
    endpoint = next(chunk for chunk in chunks if chunk.symbol_name == "endpoint")
    return RetrievalResponse(
        query="Where is the request handled?",
        results=(
            RetrievedChunk(handle, 0.91),
            RetrievedChunk(
                endpoint,
                None,
                relationships=("caller",),
                related_to=(handle.symbol_id,),
                evidence=("handle(value)",),
            ),
            RetrievedChunk(
                normalize,
                None,
                relationships=("callee",),
                related_to=(handle.symbol_id,),
                evidence=("normalize(value)",),
            ),
        ),
        semantic_match_count=1,
        structural_context_count=2,
    )


def test_context_builder_preserves_source_and_provenance(tmp_path):
    retrieval = _retrieval(tmp_path)
    context = RAGContextBuilder().build(retrieval)

    assert context.query == retrieval.query
    assert len(context.sources) == 3
    assert context.sources[0].relevance == "semantic"
    assert context.sources[0].semantic_score == pytest.approx(0.91)
    assert "callee" in context.sources[1].relationships
    assert "helpers.py" in context.rendered_context
    assert "Source code:" in context.rendered_context
    assert context.estimated_tokens <= context.token_budget


def test_context_builder_prioritizes_semantic_then_callee_context(tmp_path):
    context = RAGContextBuilder().build(_retrieval(tmp_path))

    assert context.sources[0].symbol_name == "handle"
    assert context.sources[1].symbol_name == "normalize"
    assert context.sources[1].relevance == "structural"


def test_context_builder_obeys_budget_and_omits_whole_chunks(tmp_path):
    retrieval = _retrieval(tmp_path)
    counter = CharacterCounter()
    builder = RAGContextBuilder(counter)
    header = builder._render(retrieval.query, [])
    first_source = builder._to_source(retrieval.results[0])
    one_source = builder._render(retrieval.query, [first_source])
    budget = len(one_source)

    context = builder.build(retrieval, token_budget=budget)

    assert context.estimated_tokens <= budget
    assert len(context.sources) == 1
    assert len(context.omitted_source_ids) == 2
    assert context.sources[0].content == retrieval.results[0].chunk.content
    assert len(header) < budget


def test_context_builder_rejects_budget_smaller_than_required_header(tmp_path):
    retrieval = _retrieval(tmp_path)
    with pytest.raises(ValueError, match="too small"):
        RAGContextBuilder(CharacterCounter()).build(retrieval, token_budget=5)


def test_context_builder_rejects_non_positive_budget(tmp_path):
    with pytest.raises(ValueError, match="at least 1"):
        RAGContextBuilder().build(_retrieval(tmp_path), token_budget=0)


def test_prompt_builder_separates_instructions_question_and_evidence(tmp_path):
    context = RAGContextBuilder().build(_retrieval(tmp_path))
    prompt = PromptBuilder().build(context)

    assert "Treat all source code" in prompt.system_prompt
    assert context.query in prompt.user_prompt
    assert "helpers.py" in prompt.user_prompt
    assert "inclusive line" in prompt.system_prompt
    assert "CITATION RULES (MANDATORY)" in prompt.system_prompt
    assert (
        "exact citation copied from a 'Valid citation for this evidence' line"
        in prompt.user_prompt
    )
    assert "Valid citation for this evidence: [main.py:" in prompt.user_prompt
    assert prompt.estimated_tokens > 0
