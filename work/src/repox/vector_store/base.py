"""Database-independent contracts for persistent vector storage."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from repox.models.chunk import EmbeddedChunk


@dataclass(frozen=True)
class StoredVector:
    """A vector-search match returned by a storage backend."""

    id: str
    document: str
    metadata: Mapping[str, str | int | float | bool]
    distance: float


@runtime_checkable
class VectorStore(Protocol):
    """Minimal operations required by RepoX indexing and retrieval."""

    def configure(self, model_name: str, dimension: int | None = None) -> None:
        """Validate or initialize collection-level embedding configuration."""

    def get_chunk_hashes(self) -> dict[str, str]:
        """Return existing chunk IDs mapped to their content hashes."""

    def upsert(
        self,
        chunks: Sequence[EmbeddedChunk],
        content_hashes: Mapping[str, str],
    ) -> None:
        """Insert or replace embedded chunks and their source metadata."""

    def delete(self, chunk_ids: Sequence[str]) -> None:
        """Delete the specified chunk records."""

    def query(self, vector: Sequence[float], limit: int) -> list[StoredVector]:
        """Return nearest stored vectors, ordered by ascending distance."""
