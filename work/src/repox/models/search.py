"""Typed results returned by semantic code search."""

from dataclasses import dataclass

from repox.models.chunk import CodeChunk


@dataclass(frozen=True)
class SearchResult:
    """A source-grounded chunk ranked for a natural-language query."""

    chunk: CodeChunk
    score: float
    distance: float
