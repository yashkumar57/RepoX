"""Build a stable, frontend-friendly projection of repository analysis."""

from collections import Counter

from repox.models.analysis import RepositoryAnalysis


def build_repository_visualization(analysis: RepositoryAnalysis) -> dict:
    """Return graph data and truthful aggregate metrics for dashboards.

    The projection contains no layout coordinates. Clients can choose a graph
    layout without changing the canonical graph or its source locations.
    """
    language_counts = Counter(info.language for info in analysis.files.values())
    symbol_counts = Counter(
        node.kind for node in analysis.graph.nodes.values() if node.kind != "file"
    )
    relationship_counts = Counter(edge.kind for edge in analysis.graph.edges)

    nodes = []
    for node in sorted(analysis.graph.nodes.values(), key=lambda item: item.id):
        location = node.location
        nodes.append(
            {
                "id": node.id,
                "name": node.name,
                "kind": node.kind,
                "path": node.path,
                "language": analysis.files[node.path].language,
                "start_line": location.start_line if location else None,
                "end_line": location.end_line if location else None,
            }
        )

    edges = [
        {
            "source": edge.source,
            "target": edge.target,
            "kind": edge.kind,
            "evidence": edge.evidence,
        }
        for edge in sorted(
            analysis.graph.edges,
            key=lambda item: (item.source, item.target, item.kind),
        )
    ]

    return {
        "summary": {
            "files": len(analysis.files),
            "symbols": sum(symbol_counts.values()),
            "classes": symbol_counts.get("class", 0),
            "functions": symbol_counts.get("function", 0),
            "relationships": len(analysis.graph.edges),
            "parse_errors": sum(
                len(info.parse_errors) for info in analysis.files.values()
            ),
            "scan_errors": len(analysis.scan_errors),
            "languages": dict(sorted(language_counts.items())),
            "relationship_kinds": dict(sorted(relationship_counts.items())),
        },
        "nodes": nodes,
        "edges": edges,
    }
