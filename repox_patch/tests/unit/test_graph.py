import pytest

from repox.models.graph import GraphEdge, GraphNode, RepositoryGraph


def make_node(node_id: str, kind: str = "file") -> GraphNode:
    return GraphNode(
        id=node_id,
        name=node_id.split(":")[-1],
        kind=kind,
        path="src/main.py",
    )


def test_add_node():
    graph = RepositoryGraph()
    node = make_node("file:src/main.py")

    graph.add_node(node)

    assert graph.nodes[node.id] == node


def test_add_identical_node_is_idempotent():
    graph = RepositoryGraph()
    node = make_node("file:src/main.py")

    graph.add_node(node)
    graph.add_node(node)

    assert len(graph.nodes) == 1


def test_add_conflicting_node_id_raises_error():
    graph = RepositoryGraph()

    graph.add_node(make_node("file:src/main.py"))
    conflicting = GraphNode(
        id="file:src/main.py",
        name="different.py",
        kind="file",
        path="src/different.py",
    )

    with pytest.raises(ValueError, match="Conflicting graph node ID"):
        graph.add_node(conflicting)


def test_add_edge():
    graph = RepositoryGraph()
    source = make_node("file:src/main.py")
    target = make_node("file:src/utils.py")

    graph.add_node(source)
    graph.add_node(target)

    edge = GraphEdge(
        source=source.id,
        target=target.id,
        kind="imports",
        evidence="import utils",
    )
    graph.add_edge(edge)

    assert graph.edges == [edge]


def test_add_edge_with_unknown_source_raises_error():
    graph = RepositoryGraph()
    graph.add_node(make_node("file:src/utils.py"))

    edge = GraphEdge(
        source="file:missing.py",
        target="file:src/utils.py",
        kind="imports",
    )

    with pytest.raises(ValueError, match="Unknown source node"):
        graph.add_edge(edge)


def test_add_edge_with_unknown_target_raises_error():
    graph = RepositoryGraph()
    graph.add_node(make_node("file:src/main.py"))

    edge = GraphEdge(
        source="file:src/main.py",
        target="file:missing.py",
        kind="imports",
    )

    with pytest.raises(ValueError, match="Unknown target node"):
        graph.add_edge(edge)


def test_duplicate_edge_is_ignored():
    graph = RepositoryGraph()
    source = make_node("file:src/main.py")
    target = make_node("file:src/utils.py")

    graph.add_node(source)
    graph.add_node(target)

    edge = GraphEdge(source=source.id, target=target.id, kind="imports")

    graph.add_edge(edge)
    graph.add_edge(edge)

    assert len(graph.edges) == 1


def test_neighbors_returns_outgoing_nodes():
    graph = RepositoryGraph()
    source = make_node("file:src/main.py")
    target = make_node("file:src/utils.py")

    graph.add_node(source)
    graph.add_node(target)
    graph.add_edge(GraphEdge(source=source.id, target=target.id, kind="imports"))

    assert graph.neighbors(source.id) == [target]


def test_neighbors_filters_by_relationship():
    graph = RepositoryGraph()
    source = make_node("file:src/main.py")
    imported = make_node("file:src/utils.py")
    contained = make_node("function:src/main.py:main", "function")

    for node in (source, imported, contained):
        graph.add_node(node)

    graph.add_edge(GraphEdge(source=source.id, target=imported.id, kind="imports"))
    graph.add_edge(GraphEdge(source=source.id, target=contained.id, kind="contains"))

    assert graph.neighbors(source.id, "imports") == [imported]
    assert graph.neighbors(source.id, "contains") == [contained]


def test_neighbors_unknown_node_raises_error():
    graph = RepositoryGraph()

    with pytest.raises(KeyError, match="Unknown graph node"):
        graph.neighbors("file:missing.py")


def test_validate_returns_no_errors_for_valid_graph():
    graph = RepositoryGraph()
    source = make_node("file:src/main.py")
    target = make_node("file:src/utils.py")

    graph.add_node(source)
    graph.add_node(target)
    graph.add_edge(GraphEdge(source=source.id, target=target.id, kind="imports"))

    assert graph.validate() == []
