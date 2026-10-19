from pathlib import Path

from repox.analyzers.dependencies import resolve_dependencies
from repox.scanner import scan_repository


def test_resolves_sample_repository_dependencies():
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_repo"
    scan_result = scan_repository(fixture)

    relationships = resolve_dependencies(fixture, scan_result.files)

    edges = {
        (relationship.source, relationship.target) for relationship in relationships
    }

    assert edges == {
        ("main.py", "services.py"),
        ("services.py", "database.py"),
    }


def test_resolves_absolute_imports_in_packages(tmp_path):
    from repox.scanner import scan_repository

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "routes.py").write_text(
        "def get_users():\n    return []\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from app import routes\n",
        encoding="utf-8",
    )

    scan_result = scan_repository(tmp_path)
    relationships = resolve_dependencies(tmp_path, scan_result.files)

    edges = {(r.source, r.target) for r in relationships}

    assert ("main.py", "app/routes.py") in edges


def test_resolves_relative_imports(tmp_path):
    from repox.scanner import scan_repository

    package = tmp_path / "app"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helpers.py").write_text(
        "def help_user():\n    pass\n",
        encoding="utf-8",
    )
    (package / "routes.py").write_text(
        "from .helpers import help_user\n",
        encoding="utf-8",
    )

    scan_result = scan_repository(tmp_path)
    relationships = resolve_dependencies(tmp_path, scan_result.files)

    edges = {(r.source, r.target) for r in relationships}

    assert ("app/routes.py", "app/helpers.py") in edges


def test_ignores_external_imports(tmp_path):
    from repox.scanner import scan_repository

    (tmp_path / "main.py").write_text(
        "import requests\nfrom pathlib import Path\n",
        encoding="utf-8",
    )

    scan_result = scan_repository(tmp_path)
    relationships = resolve_dependencies(tmp_path, scan_result.files)

    assert relationships == []


def test_resolves_parent_relative_imports(tmp_path):
    package = tmp_path / "app"
    subpackage = package / "routes"
    subpackage.mkdir(parents=True)

    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helpers.py").write_text(
        "def help_user():\n    pass\n", encoding="utf-8"
    )
    (subpackage / "__init__.py").write_text("", encoding="utf-8")
    (subpackage / "users.py").write_text(
        "from ..helpers import help_user\n", encoding="utf-8"
    )

    scan_result = scan_repository(tmp_path)
    relationships = resolve_dependencies(tmp_path, scan_result.files)
    edges = {(r.source, r.target) for r in relationships}

    assert ("app/routes/users.py", "app/helpers.py") in edges


def test_resolves_dotted_imports(tmp_path):
    package = tmp_path / "app"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "routes.py").write_text(
        "def get_users():\n    return []\n", encoding="utf-8"
    )
    (tmp_path / "main.py").write_text("import app.routes\n", encoding="utf-8")

    scan_result = scan_repository(tmp_path)
    relationships = resolve_dependencies(tmp_path, scan_result.files)
    edges = {(r.source, r.target) for r in relationships}

    assert ("main.py", "app/routes.py") in edges
