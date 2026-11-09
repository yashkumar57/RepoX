"""Models describing a complete repository analysis."""

from dataclasses import dataclass
from pathlib import Path

from repox.models.graph import RepositoryGraph
from repox.models.repository import FileInfo, Relationship, ScanError, ScanResult


@dataclass
class RepositoryAnalysis:
    """Combined output from the deterministic repository analysis pipeline."""

    root: Path
    scan_result: ScanResult
    import_relationships: list[Relationship]
    symbol_relationships: list[Relationship]
    relationships: list[Relationship]
    graph: RepositoryGraph
    validation_errors: list[str]

    @property
    def files(self) -> dict[str, FileInfo]:
        """Return parsed repository files."""
        return self.scan_result.files

    @property
    def scan_errors(self) -> list[ScanError]:
        """Return errors encountered while reading repository files."""
        return self.scan_result.errors

    @property
    def graph_is_valid(self) -> bool:
        """Whether the constructed graph passed structural validation."""
        return not self.validation_errors
