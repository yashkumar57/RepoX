from repox.analyzers.symbol_resolver import _resolve_import_module, resolve_symbols
from repox.models.repository import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
)


def test_resolves_same_file_function_call():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            functions=[
                FunctionInfo(name="main", calls=["calculate"]),
                FunctionInfo(name="calculate"),
            ],
        )
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].source == "function:main.py:main"
    assert relationships[0].target == "function:main.py:calculate"
    assert relationships[0].kind == "calls"


def test_resolves_imported_function_call():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            imports=[ImportInfo(module="helpers", symbol="calculate")],
            functions=[FunctionInfo(name="main", calls=["calculate"])],
        ),
        "helpers.py": FileInfo(
            path="helpers.py",
            language="python",
            functions=[FunctionInfo(name="calculate")],
        ),
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].source == "function:main.py:main"
    assert relationships[0].target == "function:helpers.py:calculate"
    assert relationships[0].kind == "calls"


def test_resolves_imported_function_alias():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            imports=[
                ImportInfo(module="helpers", symbol="calculate_total as calculate")
            ],
            functions=[FunctionInfo(name="main", calls=["calculate"])],
        ),
        "helpers.py": FileInfo(
            path="helpers.py",
            language="python",
            functions=[FunctionInfo(name="calculate_total")],
        ),
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].target == "function:helpers.py:calculate_total"


def test_resolves_class_inheritance():
    files = {
        "models.py": FileInfo(
            path="models.py",
            language="python",
            classes=[
                ClassInfo(name="BaseModel"),
                ClassInfo(name="User", bases=["BaseModel"]),
            ],
        )
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].source == "class:models.py:User"
    assert relationships[0].target == "class:models.py:BaseModel"
    assert relationships[0].kind == "inherits"


def test_does_not_resolve_ambiguous_function_names():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            functions=[
                FunctionInfo(name="main", calls=["process"]),
                FunctionInfo(name="process"),
            ],
        ),
        "other.py": FileInfo(
            path="other.py",
            language="python",
            functions=[FunctionInfo(name="process")],
        ),
    }

    relationships = resolve_symbols(files)

    assert relationships == []


def test_does_not_resolve_external_function():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            functions=[FunctionInfo(name="main", calls=["print"])],
        )
    }

    relationships = resolve_symbols(files)

    assert relationships == []


def test_resolves_absolute_import_from_src_layout():
    files = {
        "src/repox/main.py": FileInfo(
            path="src/repox/main.py",
            language="python",
        ),
        "src/repox/helpers.py": FileInfo(
            path="src/repox/helpers.py",
            language="python",
        ),
    }

    result = _resolve_import_module(
        "repox.helpers",
        "src/repox/main.py",
        files,
    )

    assert result == "src/repox/helpers.py"


def test_resolves_relative_import_from_src_layout():
    files = {
        "src/repox/analyzers/symbol_resolver.py": FileInfo(
            path="src/repox/analyzers/symbol_resolver.py",
            language="python",
        ),
        "src/repox/models/repository.py": FileInfo(
            path="src/repox/models/repository.py",
            language="python",
        ),
    }

    result = _resolve_import_module(
        "..models.repository",
        "src/repox/analyzers/symbol_resolver.py",
        files,
    )

    assert result == "src/repox/models/repository.py"


def test_resolves_function_call_through_module_alias():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            imports=[
                ImportInfo(
                    module="helpers",
                    alias="h",
                    kind="module",
                )
            ],
            functions=[FunctionInfo(name="main", calls=["h.calculate"])],
        ),
        "helpers.py": FileInfo(
            path="helpers.py",
            language="python",
            functions=[FunctionInfo(name="calculate")],
        ),
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].source == "function:main.py:main"
    assert relationships[0].target == "function:helpers.py:calculate"
    assert relationships[0].kind == "calls"


def test_resolves_function_call_through_unaliased_module_import():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            imports=[ImportInfo(module="helpers", kind="module")],
            functions=[FunctionInfo(name="main", calls=["helpers.calculate"])],
        ),
        "helpers.py": FileInfo(
            path="helpers.py",
            language="python",
            functions=[FunctionInfo(name="calculate")],
        ),
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].target == "function:helpers.py:calculate"


def test_resolves_function_call_through_src_module_alias():
    files = {
        "src/repox/main.py": FileInfo(
            path="src/repox/main.py",
            language="python",
            imports=[
                ImportInfo(
                    module="repox.helpers",
                    alias="helpers",
                    kind="module",
                )
            ],
            functions=[FunctionInfo(name="main", calls=["helpers.calculate"])],
        ),
        "src/repox/helpers.py": FileInfo(
            path="src/repox/helpers.py",
            language="python",
            functions=[FunctionInfo(name="calculate")],
        ),
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].target == ("function:src/repox/helpers.py:calculate")


def test_resolves_imported_class_alias_inheritance():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            imports=[
                ImportInfo(
                    module="models",
                    symbol="BaseModel",
                    alias="Base",
                )
            ],
            classes=[ClassInfo(name="User", bases=["Base"])],
        ),
        "models.py": FileInfo(
            path="models.py",
            language="python",
            classes=[ClassInfo(name="BaseModel")],
        ),
    }

    relationships = resolve_symbols(files)

    assert len(relationships) == 1
    assert relationships[0].source == "class:main.py:User"
    assert relationships[0].target == "class:models.py:BaseModel"
    assert relationships[0].kind == "inherits"


def test_does_not_resolve_ambiguous_import_aliases():
    files = {
        "main.py": FileInfo(
            path="main.py",
            language="python",
            imports=[
                ImportInfo(module="first", symbol="calculate"),
                ImportInfo(module="second", symbol="calculate"),
            ],
            functions=[FunctionInfo(name="main", calls=["calculate"])],
        ),
        "first.py": FileInfo(
            path="first.py",
            language="python",
            functions=[FunctionInfo(name="calculate")],
        ),
        "second.py": FileInfo(
            path="second.py",
            language="python",
            functions=[FunctionInfo(name="calculate")],
        ),
    }

    relationships = resolve_symbols(files)

    assert relationships == []


def test_does_not_treat_function_local_import_as_a_file_wide_binding(tmp_path):
    from repox.analyzers.repository_analyzer import analyze_repository

    (tmp_path / "helpers.py").write_text(
        "def calculate():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text(
        "def imported():\n"
        "    from helpers import calculate\n"
        "    return calculate()\n\n"
        "def unrelated():\n"
        "    return calculate()\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(tmp_path)

    assert analysis.files["main.py"].imports[0].scope == "local"
    assert analysis.symbol_relationships == []
