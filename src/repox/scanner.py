from pathlib import Path

from repox.models.repository import FileInfo
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


def scan_repository(root: str | Path) -> dict[str, FileInfo]:
    """Analyze Python files under a repository root."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Repository directory not found: {root}")
    results = {}
    for path in sorted(root.rglob("*.py")):
        relative_path = path.relative_to(root)
        if any(
            part in IGNORED_DIRECTORIES or part.startswith(".")
            for part in relative_path.parts[:-1]
        ):
            continue
        source = path.read_text(encoding="utf-8")
        results[relative_path.as_posix()] = parse_python(
            source,
            path=relative_path.as_posix(),
        )
    return results
