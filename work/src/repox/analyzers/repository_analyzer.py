"""Coordinate deterministic analysis of a Python repository."""

from pathlib import Path

from repox.analyzers.dependencies import resolve_dependencies
from repox.analyzers.graph_builder import build_repository_graph
from repox.analyzers.symbol_resolver import resolve_symbols
from repox.models.analysis import RepositoryAnalysis
from repox.models.repository import Relationship
from repox.scanner import scan_repository


def _deduplicate_relationships(
    relationships: list[Relationship],
) -> list[Relationship]:
    """Keep one relationship per source, target, and kind."""
    unique: dict[tuple[str, str, str], Relationship] = {}

    for relationship in relationships:
        key = (
            relationship.source,
            relationship.target,
            relationship.kind,
        )
        unique.setdefault(key, relationship)

    return list(unique.values())


def analyze_repository(root: str | Path) -> RepositoryAnalysis:
    """Run scanning, relationship resolution, and graph construction.

    The pipeline deliberately performs deterministic source analysis only.
    Embedding generation and LLM-based reasoning belong to later layers.
    """
    repository_root = Path(root).resolve()
    scan_result = scan_repository(repository_root)
    files = scan_result.files

    import_relationships = resolve_dependencies(repository_root, files)
    symbol_relationships = resolve_symbols(files)

    relationships = _deduplicate_relationships(
        import_relationships + symbol_relationships
    )
    graph = build_repository_graph(files, relationships)
    validation_errors = graph.validate()

    return RepositoryAnalysis(
        root=repository_root,
        scan_result=scan_result,
        import_relationships=import_relationships,
        symbol_relationships=symbol_relationships,
        relationships=relationships,
        graph=graph,
        validation_errors=validation_errors,
    )
