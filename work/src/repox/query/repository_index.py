"""Symbol lookup and relationship-aware repository context retrieval."""

from dataclasses import dataclass

from repox.models.analysis import RepositoryAnalysis
from repox.models.graph import EdgeKind, GraphNode, RepositoryGraph


@dataclass
class RelatedContext:
    """Structural context associated with one repository symbol."""

    symbol: GraphNode
    parent: GraphNode | None
    callers: list[GraphNode]
    callees: list[GraphNode]
    base_classes: list[GraphNode]
    subclasses: list[GraphNode]
    imports: list[GraphNode]


class RepositoryIndex:
    """Provide deterministic lookup and traversal over an analysis graph."""

    def __init__(self, analysis: RepositoryAnalysis) -> None:
        self.analysis = analysis
        self.graph: RepositoryGraph = analysis.graph

    @staticmethod
    def _qualified_name(node: GraphNode) -> str:
        """Return a symbol's qualified name without its file path."""
        if node.kind == "function":
            return node.id.split(":", 2)[-1]
        return node.name

    @staticmethod
    def _file_id(path: str) -> str:
        """Normalize a repository-relative path to a file node ID."""
        return path if path.startswith("file:") else f"file:{path}"

    def find_symbols(
        self,
        name: str,
        kind: str | None = None,
    ) -> list[GraphNode]:
        """Find symbols by exact name or qualified name.

        A short name may return multiple results. The method never selects an
        arbitrary candidate when a name is ambiguous.
        """
        query = name.strip()
        if not query:
            return []

        if kind not in {None, "class", "function"}:
            raise ValueError("kind must be 'class', 'function', or None")

        matches = []
        for node in self.graph.nodes.values():
            if node.kind not in {"class", "function"}:
                continue
            if kind is not None and node.kind != kind:
                continue

            qualified_name = self._qualified_name(node)
            if node.name == query or qualified_name == query:
                matches.append(node)

        return sorted(matches, key=lambda node: (node.path, node.id))

    def _incoming(
        self,
        node_id: str,
        relationship: EdgeKind,
    ) -> list[GraphNode]:
        if node_id not in self.graph.nodes:
            raise KeyError(f"Unknown graph node: {node_id}")

        return [
            self.graph.nodes[edge.source]
            for edge in self.graph.edges
            if edge.target == node_id and edge.kind == relationship
        ]

    def _outgoing(
        self,
        node_id: str,
        relationship: EdgeKind,
    ) -> list[GraphNode]:
        if node_id not in self.graph.nodes:
            raise KeyError(f"Unknown graph node: {node_id}")

        return [
            self.graph.nodes[edge.target]
            for edge in self.graph.edges
            if edge.source == node_id and edge.kind == relationship
        ]

    def get_callers(self, symbol_id: str) -> list[GraphNode]:
        """Return functions with call edges pointing to the given symbol."""
        return self._incoming(symbol_id, "calls")

    def get_callees(self, symbol_id: str) -> list[GraphNode]:
        """Return functions called by the given symbol."""
        return self._outgoing(symbol_id, "calls")

    def get_parent(self, symbol_id: str) -> GraphNode | None:
        """Return the containing file or class/function for a symbol."""
        parents = self._incoming(symbol_id, "contains")
        return parents[0] if parents else None

    def get_base_classes(self, class_id: str) -> list[GraphNode]:
        """Return classes inherited by the specified class."""
        return self._outgoing(class_id, "inherits")

    def get_subclasses(self, class_id: str) -> list[GraphNode]:
        """Return classes that inherit from the specified class."""
        return self._incoming(class_id, "inherits")

    def get_imports(self, file_path: str) -> list[GraphNode]:
        """Return repository files imported by the given file path."""
        file_id = self._file_id(file_path)
        return self._outgoing(file_id, "imports")

    def get_dependents(self, file_path: str) -> list[GraphNode]:
        """Return repository files that import the given file path."""
        file_id = self._file_id(file_path)
        return self._incoming(file_id, "imports")

    def get_related_context(self, symbol_id: str) -> RelatedContext:
        """Collect callers, callees, scope, inheritance, and file imports."""
        symbol = self.graph.nodes.get(symbol_id)
        if symbol is None:
            raise KeyError(f"Unknown graph node: {symbol_id}")

        if symbol.kind == "file":
            raise ValueError("Related symbol context requires a class or function")

        parent = self.get_parent(symbol_id)
        file_imports = self.get_imports(symbol.path)

        if symbol.kind == "function":
            base_classes = []
            subclasses = []
        else:
            base_classes = self.get_base_classes(symbol_id)
            subclasses = self.get_subclasses(symbol_id)

        return RelatedContext(
            symbol=symbol,
            parent=parent,
            callers=self.get_callers(symbol_id),
            callees=self.get_callees(symbol_id),
            base_classes=base_classes,
            subclasses=subclasses,
            imports=file_imports,
        )
