from pathlib import Path

import pytest

from repox.analyzers.repository_analyzer import analyze_repository
from repox.query.repository_index import RepositoryIndex

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "sample_repo"


@pytest.fixture()
def index():
    return RepositoryIndex(analyze_repository(FIXTURE_ROOT))


def test_find_symbols_returns_classes_and_functions(index):
    assert len(index.find_symbols("UserService", kind="class")) == 1
    assert len(index.find_symbols("connect", kind="function")) == 1
    assert index.find_symbols("missing_symbol") == []


def test_find_symbols_supports_qualified_function_names(index):
    matches = index.find_symbols("UserService.get_user", kind="function")

    assert len(matches) == 1
    assert matches[0].path == "services.py"


def test_find_symbols_preserves_ambiguous_matches(tmp_path):
    (tmp_path / "first.py").write_text("def shared():\n    return 1\n")
    (tmp_path / "second.py").write_text("def shared():\n    return 2\n")

    repository_index = RepositoryIndex(analyze_repository(tmp_path))

    assert len(repository_index.find_symbols("shared")) == 2


def test_get_callers_and_callees(index):
    connect = index.find_symbols("connect", kind="function")[0]
    get_user = index.find_symbols("UserService.get_user", kind="function")[0]

    assert get_user in index.get_callers(connect.id)
    assert connect in index.get_callees(get_user.id)


def test_get_parent_and_imports(index):
    get_user = index.find_symbols("UserService.get_user", kind="function")[0]

    parent = index.get_parent(get_user.id)
    imports = index.get_imports("services.py")

    assert parent is not None
    assert parent.id == "class:services.py:UserService"
    assert [node.path for node in imports] == ["database.py"]


def test_get_dependents(index):
    dependents = index.get_dependents("database.py")

    assert [node.path for node in dependents] == ["services.py"]


def test_related_context_contains_structural_information(index):
    get_user = index.find_symbols("UserService.get_user", kind="function")[0]

    context = index.get_related_context(get_user.id)

    assert context.symbol == get_user
    assert context.parent is not None
    assert context.parent.name == "UserService"
    assert [node.path for node in context.imports] == ["database.py"]


def test_unknown_symbol_raises_key_error(index):
    with pytest.raises(KeyError):
        index.get_related_context("function:missing.py:missing")
