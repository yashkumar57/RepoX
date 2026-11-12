"""Build a repository graph from parsed source metadata."""

from repox.models.graph import GraphEdge, GraphNode, RepositoryGraph
from repox.models.identifiers import (
    class_node_ids,
    function_node_ids,
    function_parent_id,
)
from repox.models.repository import FileInfo, Relationship


def build_repository_graph(
    files: dict[str, FileInfo],
    relationships: list[Relationship],
) -> RepositoryGraph:
    """Build a graph containing files, classes, functions, and imports."""
    graph = RepositoryGraph()
    class_ids = {path: class_node_ids(path, info) for path, info in files.items()}
    function_ids = {path: function_node_ids(path, info) for path, info in files.items()}

    for path in sorted(files):
        graph.add_node(
            GraphNode(
                id=f"file:{path}",
                name=path.split("/")[-1],
                kind="file",
                path=path,
            )
        )

    for path, file_info in sorted(files.items()):
        file_id = f"file:{path}"
        for class_info in file_info.classes:
            class_id = class_ids[path][id(class_info)]
            graph.add_node(
                GraphNode(
                    id=class_id,
                    name=class_info.name,
                    kind="class",
                    path=path,
                    location=class_info.location,
                )
            )
            graph.add_edge(
                GraphEdge(
                    source=file_id,
                    target=class_id,
                    kind="contains",
                    evidence=f"class {class_info.name}",
                )
            )
            for method in class_info.methods:
                method_id = function_ids[path][id(method)]
                graph.add_node(
                    GraphNode(
                        id=method_id,
                        name=method.name,
                        kind="function",
                        path=path,
                        location=method.location,
                    )
                )
                graph.add_edge(
                    GraphEdge(
                        source=class_id,
                        target=method_id,
                        kind="contains",
                        evidence=f"method {method.name}",
                    )
                )

    for path, file_info in sorted(files.items()):
        for function in file_info.functions:
            function_id = function_ids[path][id(function)]
            parent_id = function_parent_id(
                path, function, file_info, function_ids[path], class_ids[path]
            )
            graph.add_node(
                GraphNode(
                    id=function_id,
                    name=function.name,
                    kind="function",
                    path=path,
                    location=function.location,
                )
            )
            if parent_id is not None:
                graph.add_edge(
                    GraphEdge(
                        source=parent_id,
                        target=function_id,
                        kind="contains",
                        evidence=f"function {function.name}",
                    )
                )

    for relationship in relationships:
        if relationship.kind == "imports":
            source_id = f"file:{relationship.source}"
            target_id = f"file:{relationship.target}"
        else:
            source_id = relationship.source
            target_id = relationship.target
        graph.add_edge(
            GraphEdge(
                source=source_id,
                target=target_id,
                kind=relationship.kind,
                evidence=relationship.evidence,
            )
        )
    return graph
