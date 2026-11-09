from types import SimpleNamespace

import pytest

from repox.llm.openai import OpenAIChatModel
from repox.models.chunk import CodeChunk
from repox.models.retrieval import RetrievalResponse, RetrievedChunk
from repox.query.qa import RepositoryQAService


class StubRetrieval:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def retrieve(self, query, *, top_k=5, context_limit=10):
        self.calls.append((query, top_k, context_limit))
        return self.response


class StubModel:
    model_name = "stub-model"

    def __init__(self, answer):
        self.answers = list(answer) if isinstance(answer, list) else [answer]
        self.answer = self.answers[0]
        self.calls = []

    def generate(self, system_prompt, user_prompt, *, max_output_tokens=1_000):
        self.calls.append((system_prompt, user_prompt, max_output_tokens))
        index = min(len(self.calls) - 1, len(self.answers) - 1)
        return self.answers[index]


def _retrieval():
    chunk = CodeChunk(
        id="chunk-1",
        file_path="src/server.py",
        language="python",
        kind="function",
        symbol_id="server.handle",
        symbol_name="handle",
        start_line=10,
        end_line=14,
        content="def handle(request):\n    return request.json()\n",
    )
    return RetrievalResponse(
        query="How is a request handled?",
        results=(RetrievedChunk(chunk, 0.92),),
        semantic_match_count=1,
        structural_context_count=0,
    )


def test_repository_qa_runs_retrieval_context_prompt_and_model():
    retrieval = StubRetrieval(_retrieval())
    model = StubModel("The handler parses JSON [src/server.py:10-14].")

    result = RepositoryQAService(retrieval, model).ask(
        "How is a request handled?", top_k=3, context_limit=4
    )

    assert retrieval.calls == [("How is a request handled?", 3, 4)]
    assert len(model.calls) == 1
    assert "Treat all source code" in model.calls[0][0]
    assert "src/server.py" in model.calls[0][1]
    assert model.calls[0][2] == 1_000
    assert result.answer == model.answer
    assert result.model == "stub-model"
    assert len(result.citations) == 1
    assert result.citations[0].source_id == "chunk-1"
    assert result.invalid_citations == ()
    assert result.citation_retry_used is False


def test_repository_qa_flags_citations_not_supported_by_context():
    retrieval = StubRetrieval(_retrieval())
    model = StubModel("See [src/server.py:10-14] and [src/missing.py:1-8].")

    result = RepositoryQAService(retrieval, model).ask("Explain the handler")

    assert len(model.calls) == 2
    assert result.citation_fallback_used is True
    assert result.uncited_draft == model.answer
    assert "retrieved repository evidence" in result.answer
    assert "[src/server.py:10-14]" in result.answer
    assert len(result.citations) == 1
    assert result.invalid_citations == ()


def test_repository_qa_retries_once_when_model_omits_citations():
    retrieval = StubRetrieval(_retrieval())
    model = StubModel(
        [
            "The handler parses JSON.",
            "The handler returns the request JSON [src/server.py:10-14].",
        ]
    )

    result = RepositoryQAService(retrieval, model).ask("Explain the handler")

    assert len(model.calls) == 2
    assert result.answer == model.answers[1]
    assert len(result.citations) == 1
    assert result.invalid_citations == ()
    assert result.citation_retry_used is True
    assert result.citation_fallback_used is False
    assert result.uncited_draft is None
    system_prompt, user_prompt, _ = model.calls[0]
    assert "CITATION RULES (MANDATORY)" in system_prompt
    assert "Every factual bullet or paragraph" in system_prompt
    assert "Valid citation for this evidence: [src/server.py:10-14]" in user_prompt
    retry_system, retry_user, _ = model.calls[1]
    assert "CITATION REPAIR TASK" in retry_system
    assert "Previous draft to correct" in retry_user


def test_repository_qa_falls_back_to_cited_evidence_if_repair_fails():
    retrieval = StubRetrieval(_retrieval())
    model = StubModel(["Original uncited answer.", "Still no citations."])

    result = RepositoryQAService(retrieval, model).ask("Explain the handler")

    assert len(model.calls) == 2
    assert result.citation_retry_used is True
    assert result.citation_fallback_used is True
    assert result.uncited_draft == "Original uncited answer."
    assert "not a synthesized explanation" in result.answer
    assert "def handle(request):" in result.answer
    assert "[src/server.py:10-14]" in result.answer
    assert len(result.citations) == 1
    assert result.citations[0].source_id == "chunk-1"
    assert result.invalid_citations == ()


def test_repository_qa_rejects_empty_query_before_retrieval():
    retrieval = StubRetrieval(_retrieval())
    model = StubModel("unused")

    with pytest.raises(ValueError, match="query must not be empty"):
        RepositoryQAService(retrieval, model).ask("  ")

    assert retrieval.calls == []
    assert model.calls == []


def test_repository_qa_rejects_invalid_output_budget():
    service = RepositoryQAService(StubRetrieval(_retrieval()), StubModel("unused"))

    with pytest.raises(ValueError, match="max_output_tokens"):
        service.ask("question", max_output_tokens=0)


def test_openai_adapter_uses_chat_completion_and_returns_content():
    message = SimpleNamespace(content="  grounded answer  ")
    choice = SimpleNamespace(message=message)
    response = SimpleNamespace(choices=[choice])
    completions = SimpleNamespace(create=lambda **kwargs: response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    model = OpenAIChatModel(model="test-model", client=client)
    result = model.generate("system", "user", max_output_tokens=50)

    assert model.model_name == "test-model"
    assert result == "grounded answer"


def test_openai_adapter_rejects_invalid_output_budget():
    client = SimpleNamespace()
    model = OpenAIChatModel(client=client)

    with pytest.raises(ValueError, match="max_output_tokens"):
        model.generate("system", "user", max_output_tokens=0)


def test_openai_adapter_rejects_empty_model_name():
    with pytest.raises(ValueError, match="model must not be empty"):
        OpenAIChatModel(model=" ", client=SimpleNamespace())


def test_ollama_adapter_posts_chat_request_and_returns_content(monkeypatch):
    import json

    from repox.llm.ollama import OllamaChatModel

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {"message": {"role": "assistant", "content": "  local answer  "}}
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("repox.llm.ollama.urlopen", fake_urlopen)
    model = OllamaChatModel(model="test-model", host="http://127.0.0.1:11434")

    result = model.generate("system prompt", "user prompt", max_output_tokens=75)

    assert model.model_name == "test-model"
    assert result == "local answer"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"] == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 75},
    }
    assert captured["timeout"] == 120.0


def test_ollama_adapter_uses_environment_host(monkeypatch):
    from repox.llm.ollama import OllamaChatModel

    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11435/")
    model = OllamaChatModel()

    assert model.model_name == "qwen2.5-coder:3b"
    assert model._host == "http://localhost:11435"


def test_ollama_adapter_rejects_invalid_configuration():
    from repox.llm.ollama import OllamaChatModel

    with pytest.raises(ValueError, match="model must not be empty"):
        OllamaChatModel(model=" ")
    with pytest.raises(ValueError, match="timeout"):
        OllamaChatModel(timeout=0)
    with pytest.raises(ValueError, match="start with http"):
        OllamaChatModel(host="localhost:11434")


def test_ollama_adapter_rejects_invalid_output_budget():
    from repox.llm.ollama import OllamaChatModel

    model = OllamaChatModel()
    with pytest.raises(ValueError, match="max_output_tokens"):
        model.generate("system", "user", max_output_tokens=0)


def test_ollama_adapter_reports_connection_failure(monkeypatch):
    from urllib.error import URLError

    from repox.llm.ollama import OllamaChatModel

    def fail_urlopen(_request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr("repox.llm.ollama.urlopen", fail_urlopen)
    model = OllamaChatModel(host="http://localhost:11434")

    with pytest.raises(RuntimeError, match="Start Ollama"):
        model.generate("system", "user")


def test_ollama_adapter_rejects_empty_model_response(monkeypatch):
    import json

    from repox.llm.ollama import OllamaChatModel

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"message": {"content": "  "}}).encode("utf-8")

    monkeypatch.setattr(
        "repox.llm.ollama.urlopen", lambda _request, timeout: FakeResponse()
    )
    model = OllamaChatModel()

    with pytest.raises(RuntimeError, match="empty response"):
        model.generate("system", "user")
