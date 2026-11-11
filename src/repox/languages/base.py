"""Contracts for language-specific parsing and static analysis."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from repox.models.repository import FileInfo, Relationship


@runtime_checkable
class LanguageAdapter(Protocol):
    """Language-specific frontend for RepoX's shared intelligence pipeline.

    Adapters own syntax and language semantics. Their output uses RepoX's
    normalized repository models; chunking, embedding, vector storage, graph
    storage, retrieval, context construction and QA remain shared services.
    """

    language: str
    extensions: frozenset[str]

    def parse(self, source: str, *, path: str) -> FileInfo:
        """Parse source into normalized repository metadata."""

    def resolve_imports(
        self, repository_root: Path, files: dict[str, FileInfo]
    ) -> list[Relationship]:
        """Resolve language-specific imports into normalized file relationships."""

    def resolve_symbols(self, files: dict[str, FileInfo]) -> list[Relationship]:
        """Resolve language-specific symbol references into normalized relationships."""
