"""Models for bounded, source-attributed RAG context."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ContextSource:
    """One selected source chunk and its retrieval provenance."""

    source_id: str
    file_path: str
    symbol_id: str
    symbol_name: str
    kind: str
    start_line: int
    end_line: int
    content: str
    relevance: Literal["semantic", "structural"]
    semantic_score: float | None
    relationships: tuple[str, ...] = ()
    related_to: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    estimated_tokens: int = 0


@dataclass(frozen=True)
class RAGContext:
    """A token-bounded collection of repository evidence."""

    query: str
    sources: tuple[ContextSource, ...]
    rendered_context: str
    estimated_tokens: int
    token_budget: int
    omitted_source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromptPackage:
    """Provider-neutral system and user messages for an LLM request."""

    system_prompt: str
    user_prompt: str
    estimated_tokens: int
