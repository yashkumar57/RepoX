"""Scan a repository and analyze its Python files."""

from pathlib import Path

from repox.models.repository import ScanError, ScanResult
from repox.parsers.python_parser import parse_python

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


def scan_repository(root: str | Path) -> ScanResult:
    """Analyze Python files and collect file-reading errors."""
    root = Path(root).resolve()

    if not root.is_dir():
        raise NotADirectoryError(f"Repository directory not found: {root}")

    result = ScanResult()

    for path in sorted(root.rglob("*.py")):
        relative_path = path.relative_to(root)

        if any(
            part in IGNORED_DIRECTORIES or part.startswith(".")
            for part in relative_path.parts[:-1]
        ):
            continue

        relative_name = relative_path.as_posix()

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            result.errors.append(
                ScanError(
                    path=relative_name,
                    message=str(exc),
                )
            )
            continue

        result.files[relative_name] = parse_python(
            source,
            path=relative_name,
        )

    return result
