import pytest

from repox.analyzers.graph_builder import build_repository_graph
from repox.models.repository import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    Relationship,
    SourceLocation,
)


def test_builds_file_nodes():
    files = {
        "main.py": FileInfo(path="main.py", language="python"),
        "utils.py": FileInfo(path="utils.py", language="python"),
    }

    graph = build_repository_graph(files, [])

    assert "file:main.py" in graph.nodes
    assert "file:utils.py" in graph.nodes


def test_builds_class_and_method_nodes():
    method = FunctionInfo(
        name="save",
        location=SourceLocation(start_line=2, end_line=4),
        parent_class="UserService",
    )

    class_info = ClassInfo(
        name="UserService",
        methods=[method],
        location=SourceLocation(start_line=1, end_line=4),
    )

    files = {
        "services.py": FileInfo(
            path="services.py",
            language="python",
            classes=[class_info],
        )
    }

    graph = build_repository_graph(files, [])

    class_id = "class:services.py:UserService"
    method_id = "function:services.py:UserService.save"

    assert class_id in graph.nodes
    assert method_id in graph.nodes

    assert graph.neighbors("file:services.py", "contains") == [graph.nodes[class_id]]

    assert graph.neighbors(class_id, "contains") == [graph.nodes[method_id]]


def test_builds_top_level_function():
    function = FunctionInfo(name="main")

    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            functions=[function],
        )
    }

    graph = build_repository_graph(files, [])

    function_id = "function:main.py:main"

    assert function_id in graph.nodes
    assert graph.neighbors("file:main.py", "contains") == [graph.nodes[function_id]]


def test_builds_nested_function_relationship():
    outer = FunctionInfo(name="outer")
    inner = FunctionInfo(
        name="inner",
        parent_scope="outer",
    )

    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            functions=[outer, inner],
        )
    }

    graph = build_repository_graph(files, [])

    outer_id = "function:main.py:outer"
    inner_id = "function:main.py:outer.inner"

    assert outer_id in graph.nodes
    assert inner_id in graph.nodes

    assert graph.neighbors(outer_id, "contains") == [graph.nodes[inner_id]]


def test_builds_deeply_nested_function_relationship():
    functions = [
        FunctionInfo(name="outer"),
        FunctionInfo(name="middle", parent_scope="outer"),
        FunctionInfo(name="inner", parent_scope="outer.middle"),
    ]

    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            functions=functions,
        )
    }

    graph = build_repository_graph(files, [])

    middle_id = "function:main.py:outer.middle"
    inner_id = "function:main.py:outer.middle.inner"

    assert graph.neighbors("function:main.py:outer", "contains") == [
        graph.nodes[middle_id]
    ]

    assert graph.neighbors(middle_id, "contains") == [graph.nodes[inner_id]]


def test_builds_import_relationships():
    files = {
        "main.py": FileInfo(path="main.py", language="python"),
        "utils.py": FileInfo(path="utils.py", language="python"),
    }

    relationships = [
        Relationship(
            source="main.py",
            target="utils.py",
            kind="imports",
            evidence="import utils",
        )
    ]

    graph = build_repository_graph(files, relationships)

    assert graph.neighbors("file:main.py", "imports") == [graph.nodes["file:utils.py"]]


def test_rejects_relationships_with_unknown_files():
    files = {
        "main.py": FileInfo(path="main.py", language="python"),
    }

    relationships = [
        Relationship(
            source="main.py",
            target="missing.py",
            kind="imports",
        )
    ]

    with pytest.raises(ValueError, match="Unknown target node"):
        build_repository_graph(files, relationships)


def test_built_graph_passes_validation():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            functions=[
                FunctionInfo(name="main"),
                FunctionInfo(name="helper", parent_scope="main"),
            ],
        ),
        "utils.py": FileInfo(path="utils.py", language="python"),
    }

    relationships = [
        Relationship(
            source="main.py",
            target="utils.py",
            kind="imports",
        )
    ]

    graph = build_repository_graph(files, relationships)

    assert graph.validate() == []
