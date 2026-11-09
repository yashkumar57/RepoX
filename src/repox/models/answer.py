"""Models for repository-grounded question answering."""

from dataclasses import dataclass

from repox.models.context import RAGContext


@dataclass(frozen=True)
class AnswerCitation:
    """A citation validated against source chunks supplied to the model."""

    source_id: str
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class RepositoryAnswer:
    """An LLM answer together with its retrieval and citation evidence."""

    query: str
    answer: str
    model: str
    citations: tuple[AnswerCitation, ...]
    invalid_citations: tuple[str, ...]
    context: RAGContext
    citation_retry_used: bool = False
    citation_fallback_used: bool = False
    uncited_draft: str | None = None
