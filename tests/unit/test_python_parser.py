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


def test_parser_extracts_class_docstring_and_inheritance():
    source = '''\
class AdminService(BaseService, logging.Logger):
    """Manages administrative operations."""

    def delete_user(self, user_id):
        """Delete a user by ID."""
        return remove_user(user_id)
'''
    result = parse_python(source)

    admin = result.classes[0]

    assert admin.name == "AdminService"
    assert admin.bases == ["BaseService", "logging.Logger"]
    assert admin.docstring == "Manages administrative operations."
    assert admin.methods[0].docstring == "Delete a user by ID."


def test_parser_extracts_function_docstring():
    source = '''\
def calculate_total(items):
    """Calculate the total price of items."""
    return sum(items)
'''
    result = parse_python(source)

    assert result.functions[0].docstring == ("Calculate the total price of items.")


def test_parser_handles_missing_docstrings_and_inheritance():
    source = """\
class SimpleService:
    def run(self):
        return True
"""
    result = parse_python(source)

    simple = result.classes[0]

    assert simple.bases == []
    assert simple.docstring is None
    assert simple.methods[0].docstring is None


def test_parser_extracts_nested_imports():
    source = """\
def load_database():
    import sqlite3
    from database import connect
    return connect()
"""
    result = parse_python(source)

    imports = {(item.module, item.symbol) for item in result.imports}

    assert ("sqlite3", None) in imports
    assert ("database", "connect") in imports


def test_parser_extracts_nested_functions():
    source = """\
def process_user(user_id):
    def normalize_user():
        return format_name(user_id)

    return normalize_user()
"""
    result = parse_python(source)

    assert len(result.functions) == 2

    outer = next(f for f in result.functions if f.name == "process_user")
    inner = next(f for f in result.functions if f.name == "normalize_user")

    assert outer.parent_scope is None
    assert inner.parent_scope == "process_user"

    assert outer.calls == ["normalize_user"]
    assert inner.calls == ["format_name"]


def test_parser_extracts_deeply_nested_functions():
    source = """\
def outer():
    def middle():
        def inner():
            return 42
        return inner()
    return middle()
"""
    result = parse_python(source)

    nested = {f.name: f.parent_scope for f in result.functions}

    assert nested == {
        "outer": None,
        "middle": "outer",
        "inner": "outer.middle",
    }
