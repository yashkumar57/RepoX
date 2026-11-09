"""Models for hybrid semantic and structural retrieval."""

from dataclasses import dataclass

from repox.models.chunk import CodeChunk


@dataclass(frozen=True)
class RetrievedChunk:
    """A source chunk plus the evidence explaining why it was retrieved.

    ``semantic_score`` is present only for direct vector-search matches.
    Structural neighbors are context, not additional semantic matches.
    """

    chunk: CodeChunk
    semantic_score: float | None
    relationships: tuple[str, ...] = ()
    related_to: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    @property
    def is_semantic_match(self) -> bool:
        """Whether this chunk was returned directly by semantic search."""
        return self.semantic_score is not None


@dataclass(frozen=True)
class RetrievalResponse:
    """Ordered repository evidence returned for one natural-language query."""

    query: str
    results: tuple[RetrievedChunk, ...]
    semantic_match_count: int
    structural_context_count: int
