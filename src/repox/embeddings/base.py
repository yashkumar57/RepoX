"""Provider interface for interchangeable embedding backends."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Minimal interface required by RepoX's embedding pipeline."""

    model_name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed code/document passages."""

    def embed_query(self, query: str) -> list[float]:
        """Embed a natural-language retrieval query."""
