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
