from pathlib import Path

from repox.scanner import scan_repository


def test_scanner_analyzes_all_python_files():
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_repo"
    results = scan_repository(fixture)
    assert set(results) == {
        "main.py",
        "services.py",
        "database.py",
    }
    assert results["main.py"].functions[0].name == "main"
    assert results["services.py"].classes[0].name == "UserService"
    assert results["database.py"].functions[0].name == "connect"


def test_scanner_rejects_missing_directory(tmp_path):
    missing = tmp_path / "does_not_exist"
    try:
        scan_repository(missing)
    except NotADirectoryError:
        pass
    else:
        raise AssertionError("Expected NotADirectoryError")
