"""Tests for deterministic Python traceback parsing."""

from repox.debugging.traceback import parse_traceback


def test_parse_standard_python_traceback_and_exception() -> None:
    parsed = parse_traceback(
        "Traceback (most recent call last):\n"
        '  File "src/app.py", line 18, in run\n'
        "    execute()\n"
        '  File "src/service.py", line 42, in execute\n'
        "    return values[3]\n"
        "IndexError: list index out of range"
    )

    assert parsed.exception_type == "IndexError"
    assert parsed.exception_message == "list index out of range"
    assert [(frame.path, frame.line, frame.function) for frame in parsed.frames] == [
        ("src/app.py", 18, "run"),
        ("src/service.py", 42, "execute"),
    ]
    assert parsed.innermost_frame.filename == "service.py"


def test_parse_traceback_without_exception_line() -> None:
    parsed = parse_traceback('  File "worker.py", line 7, in <module>')

    assert len(parsed.frames) == 1
    assert parsed.exception_type is None
    assert parsed.raw_last_line.startswith('File "worker.py"')


def test_empty_traceback_returns_empty_analysis() -> None:
    parsed = parse_traceback(" \n")

    assert parsed.frames == ()
    assert parsed.exception_type is None
    assert parsed.raw_last_line is None


def test_exception_name_can_be_qualified() -> None:
    parsed = parse_traceback("builtins.ZeroDivisionError: division by zero")

    assert parsed.exception_type == "builtins.ZeroDivisionError"
    assert parsed.exception_message == "division by zero"


def test_extract_exception_from_description_label() -> None:
    from repox.debugging.traceback import extract_exception

    assert extract_exception(
        "Login fails\nException: AttributeError: 'NoneType' object "
        "has no attribute 'username'"
    ) == (
        "AttributeError",
        "'NoneType' object has no attribute 'username'",
    )
