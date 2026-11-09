from repox.analyzers.graph_builder import build_repository_graph
from repox.analyzers.symbol_resolver import resolve_symbols
from repox.models.repository import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    Relationship,
)


def test_graph_includes_resolved_calls_and_inheritance():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            imports=[
                ImportInfo(module="helpers", symbol="run_task"),
                ImportInfo(module="helpers", symbol="BaseService"),
            ],
            functions=[
                FunctionInfo(name="main", calls=["run_task"]),
            ],
            classes=[
                ClassInfo(name="UserService", bases=["BaseService"]),
            ],
        ),
        "helpers.py": FileInfo(
            path="helpers.py",
            language="python",
            functions=[
                FunctionInfo(name="run_task"),
            ],
            classes=[
                ClassInfo(name="BaseService"),
            ],
        ),
    }

    symbol_relationships = resolve_symbols(files)

    import_relationships = [
        Relationship(
            source="main.py",
            target="helpers.py",
            kind="imports",
            evidence="from helpers import run_task",
        )
    ]

    graph = build_repository_graph(
        files,
        import_relationships + symbol_relationships,
    )

    edges = {(edge.source, edge.target, edge.kind) for edge in graph.edges}

    assert (
        "function:main.py:main",
        "function:helpers.py:run_task",
        "calls",
    ) in edges

    assert (
        "class:main.py:UserService",
        "class:helpers.py:BaseService",
        "inherits",
    ) in edges

    assert (
        "file:main.py",
        "file:helpers.py",
        "imports",
    ) in edges

    assert graph.validate() == []
