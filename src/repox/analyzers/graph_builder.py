"""Build a repository graph from parsed source metadata."""

from repox.models.graph import GraphEdge, GraphNode, RepositoryGraph
from repox.models.repository import FileInfo, FunctionInfo, Relationship


def _function_qualified_name(function: FunctionInfo) -> str:
    """Return the lexical name of a function within its file."""
    if function.parent_scope:
        return f"{function.parent_scope}.{function.name}"

    if function.parent_class:
        return f"{function.parent_class}.{function.name}"

    return function.name


def _function_parent_id(
    path: str,
    function: FunctionInfo,
) -> str:
    """Return the graph ID of a function's lexical parent."""
    if function.parent_scope:
        return f"function:{path}:{function.parent_scope}"

    if function.parent_class:
        return f"class:{path}:{function.parent_class}"

    return f"file:{path}"


def build_repository_graph(
    files: dict[str, FileInfo],
    relationships: list[Relationship],
) -> RepositoryGraph:
    """Build a graph containing files, classes, functions, and imports."""
    graph = RepositoryGraph()

    # 1. Create file nodes.
    for path, file_info in sorted(files.items()):
        graph.add_node(
            GraphNode(
                id=f"file:{path}",
                name=path.split("/")[-1],
                kind="file",
                path=path,
            )
        )

    # 2. Create class nodes and their method nodes.
    for path, file_info in sorted(files.items()):
        file_id = f"file:{path}"

        for class_info in file_info.classes:
            class_id = f"class:{path}:{class_info.name}"

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
                qualified_name = f"{class_info.name}.{method.name}"
                method_id = f"function:{path}:{qualified_name}"

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

    # 3. Create top-level and nested function nodes.
    for path, file_info in sorted(files.items()):
        for function in file_info.functions:
            qualified_name = _function_qualified_name(function)
            function_id = f"function:{path}:{qualified_name}"
            parent_id = _function_parent_id(path, function)

            graph.add_node(
                GraphNode(
                    id=function_id,
                    name=function.name,
                    kind="function",
                    path=path,
                    location=function.location,
                )
            )

            graph.add_edge(
                GraphEdge(
                    source=parent_id,
                    target=function_id,
                    kind="contains",
                    evidence=f"function {function.name}",
                )
            )

    # 4. Convert file-level dependency relationships into graph edges.
    for relationship in relationships:
        source_id = f"file:{relationship.source}"
        target_id = f"file:{relationship.target}"

        graph.add_edge(
            GraphEdge(
                source=source_id,
                target=target_id,
                kind=relationship.kind,
                evidence=relationship.evidence,
            )
        )

    return graph
