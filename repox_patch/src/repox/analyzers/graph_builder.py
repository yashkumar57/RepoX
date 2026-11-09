"""Build a repository graph from parsed source metadata."""

from repox.models.graph import GraphEdge, GraphNode, RepositoryGraph
from repox.models.identifiers import class_node_ids, function_node_ids
from repox.models.repository import FileInfo, FunctionInfo, Relationship


def _function_qualified_name(function: FunctionInfo) -> str:
    """Return the lexical name of a function within its file."""
    if function.parent_scope:
        return f"{function.parent_scope}.{function.name}"
    if function.parent_class:
        return f"{function.parent_class}.{function.name}"
    return function.name


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
            parent_id = _parent_node_id(
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


def _parent_node_id(
    path: str,
    function: FunctionInfo,
    file_info: FileInfo,
    function_ids: dict[int, str],
    class_ids: dict[int, str],
) -> str:
    """Resolve a nested function's lexical parent to its unique definition."""
    if function.parent_scope:
        all_functions = list(file_info.functions)
        for class_info in file_info.classes:
            all_functions.extend(class_info.methods)
        candidates = [
            candidate
            for candidate in all_functions
            if _function_qualified_name(candidate) == function.parent_scope
            and candidate.location is not None
            and function.location is not None
            and candidate.location.start_line <= function.location.start_line
            and candidate.location.end_line >= function.location.end_line
        ]
        if len(candidates) == 1:
            return function_ids[id(candidates[0])]
        matching = [
            candidate
            for candidate in all_functions
            if _function_qualified_name(candidate) == function.parent_scope
        ]
        if len(matching) == 1:
            return function_ids[id(matching[0])]
        return f"function:{path}:{function.parent_scope}"
    if function.parent_class:
        candidates = [
            item for item in file_info.classes if item.name == function.parent_class
        ]
        if len(candidates) == 1:
            return class_ids[id(candidates[0])]
        return f"class:{path}:{function.parent_class}"
    return f"file:{path}"
