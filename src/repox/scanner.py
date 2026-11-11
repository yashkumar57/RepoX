"""Discover and parse repository files through registered language adapters."""

import os
from pathlib import Path

from repox.languages.registry import LanguageRegistry, default_language_registry
from repox.models.repository import ScanError, ScanResult

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}


def scan_repository(
    root: str | Path,
    registry: LanguageRegistry | None = None,
) -> ScanResult:
    """Discover supported source files and parse them with their adapter.

    The default registry intentionally enables Python only. Additional languages
    are added by registering adapters; shared indexing and retrieval services do
    not need language-specific branches.
    """
    repository_root = Path(root).resolve()

    if not repository_root.is_dir():
        raise NotADirectoryError(f"Repository directory not found: {repository_root}")

    language_registry = registry or default_language_registry()
    result = ScanResult()

    candidates: list[Path] = []
    for current_root, directories, filenames in os.walk(repository_root):
        directories[:] = sorted(
            name
            for name in directories
            if name not in IGNORED_DIRECTORIES and not name.startswith(".")
        )
        current_path = Path(current_root)
        candidates.extend(
            current_path / filename
            for filename in filenames
            if Path(filename).suffix.lower() in language_registry.extensions
        )

    for path in sorted(candidates):
        relative_path = path.relative_to(repository_root)
        relative_name = relative_path.as_posix()
        adapter = language_registry.for_path(path)
        if adapter is None:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            result.errors.append(ScanError(path=relative_name, message=str(exc)))
            continue

        try:
            result.files[relative_name] = adapter.parse(source, path=relative_name)
        except Exception as exc:
            result.errors.append(
                ScanError(
                    path=relative_name,
                    message=f"{adapter.language} parser failed: {exc}",
                )
            )

    return result
