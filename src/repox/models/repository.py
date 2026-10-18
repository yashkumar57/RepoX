from dataclasses import dataclass, field
from typing import Literal


@dataclass
class SourceLocation:
    """Location of a code element within a source file."""

    start_line: int
    end_line: int


@dataclass
class ImportInfo:
    """An import statement discovered in a source file."""

    module: str
    symbol: str | None = None
    location: SourceLocation | None = None


@dataclass
class FunctionInfo:
    """Metadata extracted from a function or method."""

    name: str
    parameters: list[str] = field(default_factory=list)
    return_expressions: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    location: SourceLocation | None = None
    parent_class: str | None = None


@dataclass
class ClassInfo:
    """Metadata extracted from a class."""

    name: str
    methods: list[FunctionInfo] = field(default_factory=list)
    location: SourceLocation | None = None


@dataclass
class FileInfo:
    """Structured analysis of a source file."""

    path: str
    language: str
    imports: list[ImportInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    """A relationship between two repository entities."""

    source: str
    target: str
    kind: Literal[
        "imports",
        "calls",
        "contains",
        "inherits",
    ]
    evidence: str | None = None


@dataclass
class ScanError:
    """A file-level error encountered during repository scanning."""

    path: str
    message: str


@dataclass
class ScanResult:
    """Results and diagnostics produced by a repository scan."""

    files: dict[str, FileInfo] = field(default_factory=dict)
    errors: list[ScanError] = field(default_factory=list)
