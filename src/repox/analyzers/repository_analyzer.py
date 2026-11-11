"""Coordinate language adapters and the shared repository analysis pipeline."""

from pathlib import Path

from repox.analyzers.graph_builder import build_repository_graph
from repox.languages.registry import LanguageRegistry, default_language_registry
from repox.models.analysis import RepositoryAnalysis
from repox.models.repository import Relationship
from repox.scanner import scan_repository


def _deduplicate_relationships(
    relationships: list[Relationship],
) -> list[Relationship]:
    """Keep one relationship per source, target, and kind."""
    unique: dict[tuple[str, str, str], Relationship] = {}
    for relationship in relationships:
        key = (relationship.source, relationship.target, relationship.kind)
        unique.setdefault(key, relationship)
    return list(unique.values())


def analyze_repository(
    root: str | Path,
    registry: LanguageRegistry | None = None,
) -> RepositoryAnalysis:
    """Run adapter-owned parsing/resolution and shared graph construction.

    Each registered adapter owns syntax and language semantics. Normalized
    ``FileInfo`` and ``Relationship`` records then flow through the same graph,
    chunking, embedding, vector indexing and retrieval pipeline.
    """
    repository_root = Path(root).resolve()
    language_registry = registry or default_language_registry()
    scan_result = scan_repository(repository_root, language_registry)
    files = scan_result.files

    import_relationships: list[Relationship] = []
    symbol_relationships: list[Relationship] = []
    adapters = {}
    for info in files.values():
        adapter = language_registry.get(info.language)
        adapters[adapter.language] = adapter
    for language in sorted(adapters):
        adapter = adapters[language]
        import_relationships.extend(adapter.resolve_imports(repository_root, files))
        symbol_relationships.extend(adapter.resolve_symbols(files))

    import_relationships = _deduplicate_relationships(import_relationships)
    symbol_relationships = _deduplicate_relationships(symbol_relationships)
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
