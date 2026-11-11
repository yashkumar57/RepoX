"""Python reference adapter for RepoX's language-neutral pipeline."""

from pathlib import Path

from repox.analyzers.dependencies import resolve_dependencies
from repox.analyzers.symbol_resolver import resolve_symbols
from repox.models.repository import FileInfo, Relationship
from repox.parsers.python_parser import parse_python


class PythonLanguageAdapter:
    """Python parser and resolver adapter backed by the standard-library AST."""

    language = "python"
    extensions = frozenset({".py", ".pyw"})

    def parse(self, source: str, *, path: str) -> FileInfo:
        return parse_python(source, path=path)

    def resolve_imports(
        self, repository_root: Path, files: dict[str, FileInfo]
    ) -> list[Relationship]:
        python_files = {
            path: info for path, info in files.items() if info.language == self.language
        }
        return resolve_dependencies(repository_root, python_files)

    def resolve_symbols(self, files: dict[str, FileInfo]) -> list[Relationship]:
        python_files = {
            path: info for path, info in files.items() if info.language == self.language
        }
        return resolve_symbols(python_files)
