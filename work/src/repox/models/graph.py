"""Core graph data structures for repository analysis."""

from dataclasses import dataclass, field
from typing import Literal

from repox.models.repository import SourceLocation

NodeKind = Literal["file", "class", "function"]
EdgeKind = Literal["imports", "calls", "contains", "inherits"]


@dataclass
class GraphNode:
    """A file, class, or function represented in the repository graph."""

    id: str
    name: str
    kind: NodeKind
    path: str
    location: SourceLocation | None = None


@dataclass
class GraphEdge:
    """A directed relationship between two graph nodes."""

    source: str
    target: str
    kind: EdgeKind
    evidence: str | None = None


@dataclass
class RepositoryGraph:
    """Graph representation of a repository."""

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        """Add a node, rejecting conflicting duplicate identifiers."""
        existing = self.nodes.get(node.id)

        if existing is not None and existing != node:
            raise ValueError(f"Conflicting graph node ID: {node.id}")

        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge after validating its endpoints."""
        if edge.source not in self.nodes:
            raise ValueError(f"Unknown source node: {edge.source}")

        if edge.target not in self.nodes:
            raise ValueError(f"Unknown target node: {edge.target}")

        key = (edge.source, edge.target, edge.kind)

        if any(
            (existing.source, existing.target, existing.kind) == key
            for existing in self.edges
        ):
            return

        self.edges.append(edge)

    def neighbors(
        self,
        node_id: str,
        relationship: EdgeKind | None = None,
    ) -> list[GraphNode]:
        """Return nodes reached by outgoing edges."""
        if node_id not in self.nodes:
            raise KeyError(f"Unknown graph node: {node_id}")

        result = []

        for edge in self.edges:
            if edge.source != node_id:
                continue

            if relationship is not None and edge.kind != relationship:
                continue

            result.append(self.nodes[edge.target])

        return result

    def validate(self) -> list[str]:
        """Return structural problems found in the graph."""
        errors = []

        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(f"Missing source node: {edge.source}")

            if edge.target not in self.nodes:
                errors.append(f"Missing target node: {edge.target}")

        return errors
