from pathlib import Path

from repox.analyzers.dependencies import resolve_dependencies
from repox.scanner import scan_repository


def test_resolves_sample_repository_dependencies():
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_repo"
    files = scan_repository(fixture)
    relationships = resolve_dependencies(fixture, files)
    actual = {
        (relationship.source, relationship.target, relationship.kind)
        for relationship in relationships
    }
    assert actual == {
        ("main.py", "services.py", "imports"),
        ("services.py", "database.py", "imports"),
    }
