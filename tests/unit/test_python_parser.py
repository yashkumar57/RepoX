from repox.parsers.python_parser import parse_python


def test_parser_extracts_imports_classes_and_methods():
    source = """\
from database import connect
class UserService:
    def get_user(self, user_id):
        return connect(user_id)
"""
    result = parse_python(source, "services/user.py")
    assert result.path == "services/user.py"
    assert result.language == "python"

    assert result.imports[0].module == "database"
    assert result.imports[0].symbol == "connect"

    assert result.classes[0].name == "UserService"

    method = result.classes[0].methods[0]
    assert method.name == "get_user"
    assert method.parameters == ["self", "user_id"]
    assert method.calls == ["connect"]
    assert method.return_expressions == ["connect(user_id)"]
    assert method.parent_class == "UserService"


def test_parser_extracts_top_level_functions():
    source = """\
def greet(name):
    return format_name(name)
"""
    result = parse_python(source)
    assert len(result.functions) == 1
    function = result.functions[0]
    assert function.name == "greet"
    assert function.parameters == ["name"]
    assert function.calls == ["format_name"]
    assert function.return_expressions == ["format_name(name)"]


def test_parser_records_source_locations():
    source = """\
class Example:
    def run(self):
        return 42
"""
    result = parse_python(source)
    example = result.classes[0]
    method = example.methods[0]
    assert example.location.start_line == 1
    assert method.location.start_line == 2
    assert method.location.end_line == 3


def test_parser_reports_syntax_errors():
    source = """\
def greet(name)
    return name
"""

    result = parse_python(source, "broken.py")

    assert result.path == "broken.py"
    assert result.parse_errors
    assert any("line" in error.lower() for error in result.parse_errors)
