"""Tests for repository-grounded debugging orchestration."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from repox.context import RAGContextBuilder
from repox.debugging.service import DebuggingService


def _qa_with_model() -> Mock:
    qa = Mock()
    qa.context_builder = RAGContextBuilder()
    qa.model = Mock()
    qa.model.model_name = "qwen2.5-coder:7b"
    qa.model.generate.return_value = (
        "The exception indicates that a value is None when username is accessed."
    )
    return qa


def test_debug_service_passes_description_and_traceback_facts_to_qa() -> None:
    qa = Mock()
    qa.ask.return_value = SimpleNamespace(answer="Likely cause", model="test-model")
    service = DebuggingService(qa)

    result = service.analyze(
        description="The request fails for an empty list.",
        traceback_text=(
            "Traceback (most recent call last):\n"
            '  File "src/worker.py", line 12, in run\n'
            "IndexError: list index out of range"
        ),
    )

    assert result.traceback.exception_type == "IndexError"
    assert result.traceback.innermost_frame.path == "src/worker.py"
    query = qa.ask.call_args.args[0]
    assert "empty list" in query
    assert "IndexError" in query
    assert "src/worker.py:12 in run" in query
    assert "Separate directly observed facts from hypotheses" in query


def test_debug_service_uses_model_for_description_without_traceback() -> None:
    qa = _qa_with_model()

    result = DebuggingService(qa).analyze(
        description=(
            "Authentication fails.\nException: AttributeError: 'NoneType' object "
            "has no attribute 'username'"
        )
    )

    assert result.traceback.frames == ()
    assert result.traceback.exception_type == "AttributeError"
    qa.ask.assert_not_called()
    qa.model.generate.assert_called_once()
    assert "NoneType" in qa.model.generate.call_args.args[1]
    assert "username" in qa.model.generate.call_args.args[1]
    assert result.answer.model == "qwen2.5-coder:7b"
    assert result.answer.citations == ()
    assert "Repository evidence status: unavailable" in result.answer.answer


def test_debug_service_requires_description_or_traceback() -> None:
    with pytest.raises(ValueError, match="Provide a bug description"):
        DebuggingService(Mock()).analyze()


def test_debug_service_does_not_query_unrelated_repository_without_frames() -> None:
    qa = _qa_with_model()

    result = DebuggingService(qa).analyze(
        description="get_username crashes when user.profile is missing",
        traceback_text=(
            "AttributeError: 'NoneType' object has no attribute 'username'"
        ),
    )

    qa.ask.assert_not_called()
    qa.model.generate.assert_called_once()
    assert result.answer.citations == ()
    assert "Repository evidence status: unavailable" in result.answer.answer
    assert "username" in result.answer.answer


def test_unmapped_traceback_gets_model_diagnosis_without_citations() -> None:
    from repox.debugging.traceback import TracebackAnalysis, TracebackFrame

    qa = _qa_with_model()
    service = DebuggingService(qa)
    parsed = TracebackAnalysis(
        frames=(
            TracebackFrame(
                path="app/auth.py",
                line=16,
                function="get_user_profile",
            ),
        ),
        exception_type="AttributeError",
        exception_message="'NoneType' object has no attribute 'profile'",
        raw_last_line=("AttributeError: 'NoneType' object has no attribute 'profile'"),
    )

    answer = service._no_matching_source_answer(
        "The user lookup returned None.", parsed, token_budget=8_000
    )

    qa.model.generate.assert_called_once()
    assert answer.model == "qwen2.5-coder:7b"
    assert answer.citations == ()
    assert answer.answer.count("Repository evidence status:") == 1
    assert "Repository evidence status: no matching source frame" in answer.answer
    assert "app/auth.py:16" in qa.model.generate.call_args.args[1]
    system_prompt = qa.model.generate.call_args.args[0]
    assert "Treat explanations about return values" in system_prompt
    assert "Never state that a function returns None" in system_prompt


def test_traceback_source_mapping_prefers_narrowest_function_chunk(tmp_path):
    from pathlib import Path

    from repox.analyzers.repository_analyzer import analyze_repository
    from repox.debugging.traceback import TracebackAnalysis, TracebackFrame

    root = Path(tmp_path) / "repo"
    (root / "src" / "app").mkdir(parents=True)
    source = (
        "def authenticate_user(user_id):\n"
        "    return get_user_profile(user_id).username\n\n"
        "def get_user_profile(user_id):\n"
        "    user = users.get(user_id)\n"
        "    return user.profile\n"
    )
    (root / "src" / "app" / "auth.py").write_text(source, encoding="utf-8")
    analysis = analyze_repository(root)
    qa = SimpleNamespace(retrieval=SimpleNamespace(analysis=analysis))
    service = DebuggingService(qa)
    parsed = TracebackAnalysis(
        frames=(TracebackFrame("app/auth.py", 6, "get_user_profile"),),
        exception_type="AttributeError",
        exception_message="'NoneType' object has no attribute 'profile'",
        raw_last_line="AttributeError: 'NoneType' object has no attribute 'profile'",
    )

    response = service._retrieve_traceback_evidence("debug", parsed, context_limit=8)

    assert len(response.results) == 1
    chunk = response.results[0].chunk
    assert chunk.kind == "function"
    assert chunk.symbol_name == "get_user_profile"
    assert "return user.profile" in chunk.content
    assert response.results[0].evidence == (
        "Exact traceback location mapped to src/app/auth.py:6",
    )


def test_traceback_source_mapping_rejects_ambiguous_suffixes(tmp_path):
    from pathlib import Path

    from repox.analyzers.repository_analyzer import analyze_repository
    from repox.debugging.traceback import TracebackAnalysis, TracebackFrame

    root = Path(tmp_path) / "repo"
    for package in ("first", "second"):
        directory = root / package
        directory.mkdir(parents=True)
        (directory / "auth.py").write_text(
            "def authenticate():\n    return None\n", encoding="utf-8"
        )
    analysis = analyze_repository(root)
    qa = SimpleNamespace(retrieval=SimpleNamespace(analysis=analysis))
    service = DebuggingService(qa)
    parsed = TracebackAnalysis(
        frames=(TracebackFrame("auth.py", 2, "authenticate"),),
        exception_type="RuntimeError",
        exception_message="failure",
        raw_last_line="RuntimeError: failure",
    )

    response = service._retrieve_traceback_evidence("debug", parsed, context_limit=8)

    assert response.results == ()


def test_unmapped_diagnosis_prompt_avoids_unproven_return_and_default_identity():
    qa = _qa_with_model()

    DebuggingService(qa).analyze(
        description=(
            "Authentication fails with AttributeError: 'NoneType' object has "
            "has no attribute 'username'"
        )
    )

    system_prompt = qa.model.generate.call_args.args[0]
    assert "receiver of the failing attribute access was None" in system_prompt
    assert "Do not suggest a default identity or username" in system_prompt


def test_description_only_debug_uses_semantic_repository_candidates(tmp_path):
    from repox.analyzers.repository_analyzer import analyze_repository
    from repox.chunking.semantic_chunker import chunk_repository
    from repox.models.search import SearchResult
    from repox.query.qa import RepositoryQAService
    from repox.query.retrieval import RepositoryRetrievalService

    root = tmp_path / "repo"
    root.mkdir()
    source = (
        "def merge_sort(values):\n"
        "    if len(values) <= 1:\n"
        "        return values\n"
        "    middle = len(values) // 2\n"
        "    left = merge_sort(values[:middle])\n"
        "    right = merge_sort(values[middle:])\n"
        "    return merge(left, right)\n"
    )
    (root / "sorting.py").write_text(source, encoding="utf-8")
    analysis = analyze_repository(root)
    chunk = next(
        item for item in chunk_repository(analysis) if item.symbol_name == "merge_sort"
    )

    class Search:
        def search(self, query, top_k=5):
            assert "duplicate" in query.lower()
            return [SearchResult(chunk, score=0.91, distance=0.09)]

    class Model:
        model_name = "test-model"

        def generate(self, system_prompt, user_prompt, *, max_output_tokens=1000):
            return (
                "The merge_sort function recursively splits the input before "
                f"merging the results [sorting.py:{chunk.start_line}-{chunk.end_line}]."
            )

    retrieval = RepositoryRetrievalService(analysis, Search())
    qa = RepositoryQAService(retrieval, Model())
    result = DebuggingService(qa).analyze(
        description=(
            "Sorting produces incorrect output when duplicate values are present."
        )
    )

    assert result.traceback.frames == ()
    assert len(result.answer.citations) == 1
    assert "No traceback was supplied" in result.answer.answer
    assert "merge_sort" in result.answer.answer
