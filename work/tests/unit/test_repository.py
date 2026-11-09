from repox.models.repository import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    Relationship,
    SourceLocation,
)


def test_function_info_stores_metadata():
    function = FunctionInfo(
        name="get_user",
        parameters=["self", "user_id"],
        return_expressions=["connect(user_id)"],
        calls=["connect"],
        location=SourceLocation(start_line=4, end_line=5),
        parent_class="UserService",
    )

    assert function.name == "get_user"
    assert function.parameters == ["self", "user_id"]
    assert function.return_expressions == ["connect(user_id)"]
    assert function.calls == ["connect"]
    assert function.parent_class == "UserService"


def test_file_info_stores_imports_and_classes():
    file = FileInfo(
        path="src/services/user.py",
        language="python",
        imports=[ImportInfo(module="database", symbol="connect")],
        classes=[ClassInfo(name="UserService")],
    )
    assert file.path == "src/services/user.py"
    assert file.language == "python"
    assert file.imports[0].module == "database"
    assert file.classes[0].name == "UserService"


def test_relationship_records_dependency_evidence():
    relationship = Relationship(
        source="services/user.py",
        target="database.py",
        kind="imports",
        evidence="from database import connect",
    )
    assert relationship.source == "services/user.py"
    assert relationship.target == "database.py"
    assert relationship.kind == "imports"
    assert relationship.evidence == "from database import connect"


def test_function_default_lists_are_independent():
    first = FunctionInfo(name="first")
    second = FunctionInfo(name="second")
    first.parameters.append("user_id")
    assert second.parameters == []
