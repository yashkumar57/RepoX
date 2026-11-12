"""Focused Python-only acceptance coverage for the Day 20 demonstration."""

from pathlib import Path

from repox.debugging.service import DebuggingService
from repox.indexing.search import SemanticSearchService
from repox.indexing.service import RepositoryIndexingService
from repox.models.chunk import EmbeddedChunk
from repox.query.qa import RepositoryQAService
from repox.query.retrieval import RepositoryRetrievalService
from repox.vector_store.base import StoredVector


class DemoProvider:
    model_name = "demo-python-provider"
    dimension = 2

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, query):
        return [1.0, 0.0]


class DemoStore:
    def __init__(self):
        self.hashes = {}
        self.records = {}

    def configure(self, model_name, dimension=None):
        assert model_name == "demo-python-provider"
        assert dimension in {None, 2}

    def get_chunk_hashes(self):
        return dict(self.hashes)

    def upsert(self, chunks: list[EmbeddedChunk], content_hashes):
        for item in chunks:
            chunk = item.chunk
            self.hashes[chunk.id] = content_hashes[chunk.id]
            self.records[chunk.id] = StoredVector(
                id=chunk.id,
                document=chunk.content,
                metadata={
                    "file_path": chunk.file_path,
                    "language": chunk.language,
                    "kind": chunk.kind,
                    "symbol_id": chunk.symbol_id,
                    "symbol_name": chunk.symbol_name,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "parent_symbol_id": chunk.parent_symbol_id or "",
                },
                distance=0.1 if chunk.symbol_name == "handle_user" else 0.5,
            )

    def delete(self, chunk_ids):
        for chunk_id in chunk_ids:
            self.hashes.pop(chunk_id, None)
            self.records.pop(chunk_id, None)

    def query(self, vector, limit):
        return sorted(self.records.values(), key=lambda item: item.distance)[:limit]


class CitedModel:
    model_name = "demo-model"

    def generate(self, system_prompt, user_prompt, *, max_output_tokens=1000):
        return "handle_user delegates normalization [main.py:3-4]."


def test_day20_python_pipeline_indexes_retrieves_answers_and_debugs(tmp_path: Path):
    (tmp_path / "helpers.py").write_text(
        "def normalize(value):\n    return value.strip()\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text(
        "from helpers import normalize\n\n"
        "def handle_user(value):\n"
        "    return normalize(value)\n",
        encoding="utf-8",
    )
    store = DemoStore()
    provider = DemoProvider()
    indexed = RepositoryIndexingService(store, provider).index(tmp_path)

    assert indexed.analyzed_files == 2
    assert indexed.relationships == 2  # one import and one explicit function call
    assert indexed.report.embedded_chunks == indexed.report.total_chunks

    from repox.analyzers.repository_analyzer import analyze_repository

    analysis = analyze_repository(tmp_path)
    retrieval = RepositoryRetrievalService(
        analysis, SemanticSearchService(store, provider)
    )
    evidence = retrieval.retrieve("where is user input normalized?", context_limit=5)

    assert evidence.results[0].chunk.symbol_name == "handle_user"
    assert any("callee" in item.relationships for item in evidence.results)

    qa = RepositoryQAService(retrieval, CitedModel())
    answer = qa.ask("How is user input normalized?", context_limit=5)
    assert answer.citations[0].file_path == "main.py"

    debug = DebuggingService(qa).analyze(
        traceback_text=(
            "Traceback (most recent call last):\n"
            '  File "main.py", line 4, in handle_user\n'
            "AttributeError: value is invalid"
        )
    )
    assert debug.traceback.innermost_frame.path == "main.py"
    assert debug.answer.citations[0].file_path == "main.py"
