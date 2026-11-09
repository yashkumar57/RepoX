from pathlib import Path

import pytest

from repox.scanner import scan_repository


def test_scanner_analyzes_all_python_files():
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_repo"

    result = scan_repository(fixture)

    assert set(result.files) == {
        "main.py",
        "services.py",
        "database.py",
    }
    assert result.files["main.py"].functions[0].name == "main"
    assert result.files["services.py"].classes[0].name == "UserService"
    assert result.files["database.py"].functions[0].name == "connect"
    assert result.errors == []


def test_scanner_rejects_missing_directory(tmp_path):
    missing = tmp_path / "does_not_exist"

    with pytest.raises(NotADirectoryError):
        scan_repository(missing)


def test_scanner_continues_after_file_read_error(tmp_path, monkeypatch):
    good_file = tmp_path / "good.py"
    bad_file = tmp_path / "bad.py"

    good_file.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    bad_file.write_text("def broken():\n    pass\n", encoding="utf-8")

    original_read_text = Path.read_text

    def mock_read_text(path, *args, **kwargs):
        if path == bad_file:
            raise OSError("Simulated read failure")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", mock_read_text)

    result = scan_repository(tmp_path)

    assert set(result.files) == {"good.py"}
    assert len(result.errors) == 1
    assert result.errors[0].path == "bad.py"
    assert "Simulated read failure" in result.errors[0].message


def test_scanner_reports_invalid_utf8(tmp_path, monkeypatch):
    source_file = tmp_path / "invalid.py"
    source_file.write_bytes(b"\xff\xfe\xfa")

    result = scan_repository(tmp_path)

    assert "invalid.py" not in result.files
    assert len(result.errors) == 1
    assert result.errors[0].path == "invalid.py"
    assert result.errors[0].message
