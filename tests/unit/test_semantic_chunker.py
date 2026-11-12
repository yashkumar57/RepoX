from pathlib import Path

import pytest

from repox.analyzers.repository_analyzer import analyze_repository
from repox.chunking import chunk_repository, subdivide_chunks
from repox.models.chunk import CodeChunk

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "sample_repo"


def test_chunk_repository_creates_symbol_and_module_chunks():
    analysis = analyze_repository(FIXTURE_ROOT)
    chunks = chunk_repository(analysis)

    assert any(
        chunk.kind == "class" and chunk.symbol_name == "UserService" for chunk in chunks
    )
    assert any(
        chunk.kind == "function" and chunk.symbol_name == "UserService.get_user"
        for chunk in chunks
    )
    assert any(
        chunk.kind == "function" and chunk.symbol_name == "connect" for chunk in chunks
    )
    assert any(
        chunk.kind == "module" and chunk.file_path == "main.py" for chunk in chunks
    )


def test_symbol_chunks_preserve_graph_ids_and_parent_relationships():
    chunks = chunk_repository(analyze_repository(FIXTURE_ROOT))
    method = next(
        chunk for chunk in chunks if chunk.symbol_name == "UserService.get_user"
    )

    assert method.symbol_id == "function:services.py:UserService.get_user"
    assert method.parent_symbol_id == "class:services.py:UserService"
    assert method.start_line == 5
    assert "return connect(user_id)" in method.content


def test_chunk_ids_are_deterministic():
    analysis = analyze_repository(FIXTURE_ROOT)
    first = chunk_repository(analysis)
    second = chunk_repository(analysis)
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]


def test_module_chunks_exclude_function_definitions(tmp_path):
    source = (
        "import math\n\n"
        "CONSTANT = 10\n\n"
        "def calculate(value):\n"
        "    return math.sqrt(value) + CONSTANT\n\n"
        "result = calculate(25)\n"
    )
    (tmp_path / "example.py").write_text(source, encoding="utf-8")

    chunks = chunk_repository(analyze_repository(tmp_path))
    module_chunks = [chunk for chunk in chunks if chunk.kind == "module"]
    function_chunks = [chunk for chunk in chunks if chunk.kind == "function"]
    module_content = "\n".join(chunk.content for chunk in module_chunks)

    assert len(function_chunks) == 1
    assert "def calculate" not in module_content
    assert "import math" in module_content
    assert "result = calculate(25)" in module_content


def test_class_and_method_chunks_keep_exact_source(tmp_path):
    source = (
        "class Example:\n"
        '    """Example class."""\n'
        "\n"
        "    def run(self):\n"
        "        return 42\n"
    )
    (tmp_path / "example.py").write_text(source, encoding="utf-8")

    chunks = chunk_repository(analyze_repository(tmp_path))
    class_chunk = next(chunk for chunk in chunks if chunk.kind == "class")
    method_chunk = next(chunk for chunk in chunks if chunk.kind == "function")

    assert class_chunk.start_line == 1
    assert class_chunk.end_line == 5
    assert '"""Example class."""' in class_chunk.content
    assert "def run(self):" in class_chunk.content
    assert method_chunk.start_line == 4
    assert method_chunk.end_line == 5
    assert method_chunk.content == "    def run(self):\n        return 42"


def test_embedding_text_includes_source_metadata():
    chunks = chunk_repository(analyze_repository(FIXTURE_ROOT))
    connect = next(chunk for chunk in chunks if chunk.symbol_name == "connect")

    assert "Language: python" in connect.embedding_text
    assert "File: database.py" in connect.embedding_text
    assert "Symbol: connect" in connect.embedding_text
    assert "Source lines:" in connect.embedding_text
    assert "def connect" in connect.embedding_text


def test_chunking_rejects_source_changed_after_analysis(tmp_path):
    source_path = tmp_path / "example.py"
    source_path.write_text("def original():\n    return 1\n", encoding="utf-8")
    analysis = analyze_repository(tmp_path)

    source_path.write_text("def replacement():\n    return 2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Source changed since analysis"):
        chunk_repository(analysis)


def test_duplicate_definitions_use_their_canonical_graph_symbol_ids(tmp_path):
    (tmp_path / "example.py").write_text(
        "class Duplicate:\n"
        "    def run(self):\n"
        "        return 1\n\n"
        "class Duplicate:\n"
        "    def run(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(tmp_path)
    chunks = chunk_repository(analysis)
    symbol_chunks = [chunk for chunk in chunks if chunk.kind != "module"]
    function_chunks = [chunk for chunk in chunks if chunk.kind == "function"]

    assert len(symbol_chunks) == 4
    assert all(chunk.symbol_id in analysis.graph.nodes for chunk in symbol_chunks)
    assert all(
        chunk.parent_symbol_id in analysis.graph.nodes for chunk in function_chunks
    )
    assert all("@" in chunk.symbol_id for chunk in symbol_chunks)


def test_duplicate_classes_keep_canonical_nested_parent_ids(tmp_path):
    (tmp_path / "example.py").write_text(
        "class Duplicate:\n"
        "    def run(self):\n"
        "        def inner():\n"
        "            return 1\n"
        "        return inner()\n\n"
        "class Duplicate:\n"
        "    def run(self):\n"
        "        def inner():\n"
        "            return 2\n"
        "        return inner()\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(tmp_path)
    graph = analysis.graph
    chunks = chunk_repository(analysis)
    class_ids = sorted(node.id for node in graph.nodes.values() if node.kind == "class")
    method_ids = sorted(
        node.id
        for node in graph.nodes.values()
        if node.kind == "function" and node.name == "run"
    )
    inner_ids = sorted(
        node.id
        for node in graph.nodes.values()
        if node.kind == "function" and node.name == "inner"
    )

    assert all("@" in symbol_id for symbol_id in [*class_ids, *method_ids, *inner_ids])
    for class_id, method_id, inner_id in zip(
        class_ids, method_ids, inner_ids, strict=True
    ):
        assert graph.neighbors(class_id, "contains") == [graph.nodes[method_id]]
        assert graph.neighbors(method_id, "contains") == [graph.nodes[inner_id]]
    assert all(
        edge.source in graph.nodes and edge.target in graph.nodes
        for edge in graph.edges
    )
    assert graph.validate() == []

    chunks_by_symbol = {chunk.symbol_id: chunk for chunk in chunks}
    for method_id, inner_id in zip(method_ids, inner_ids, strict=True):
        assert chunks_by_symbol[method_id].parent_symbol_id in class_ids
        assert chunks_by_symbol[inner_id].parent_symbol_id == method_id


def test_subdivide_chunks_uses_provider_tokens_and_keeps_source_ranges():
    chunk = CodeChunk(
        id="chunk:long",
        file_path="example.py",
        language="python",
        kind="function",
        symbol_id="function:example.py:long_running",
        symbol_name="long_running",
        start_line=10,
        end_line=14,
        content="\n".join(f"    value += {number}" for number in range(5)),
        parent_symbol_id="file:example.py",
    )

    def count_tokens(text):
        return len(text.split())

    pieces = subdivide_chunks([chunk], max_tokens=25, count_tokens=count_tokens)

    assert len(pieces) > 1
    assert all(count_tokens(piece.embedding_text) <= 25 for piece in pieces)
    assert "\n".join(piece.content for piece in pieces) == chunk.content
    assert [(piece.start_line, piece.end_line) for piece in pieces] == [
        (10, 11),
        (12, 13),
        (14, 14),
    ]
