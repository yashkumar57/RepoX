"""Models for source-grounded semantic code chunks."""

from dataclasses import dataclass
from typing import Literal

ChunkKind = Literal["module", "class", "function"]


@dataclass(frozen=True)
class CodeChunk:
    """A source-code unit with stable identity and structural metadata.

    Class and enclosing-function chunks may contain child-function source.
    This deliberate overlap preserves both broad and precise retrieval targets.
    """

    id: str
    file_path: str
    language: str
    kind: ChunkKind
    symbol_id: str
    symbol_name: str
    start_line: int
    end_line: int
    content: str
    parent_symbol_id: str | None = None

    @property
    def embedding_text(self) -> str:
        """Return metadata-enriched text to encode for semantic retrieval."""
        metadata = [
            f"Language: {self.language}",
            f"File: {self.file_path}",
            f"Code element: {self.kind}",
            f"Symbol: {self.symbol_name}",
        ]
        if self.parent_symbol_id is not None:
            metadata.append(f"Parent symbol ID: {self.parent_symbol_id}")
        metadata.append(f"Source lines: {self.start_line}-{self.end_line}")
        metadata.extend(["Source code:", self.content])
        return "\n".join(metadata)


@dataclass(frozen=True)
class EmbeddedChunk:
    """A code chunk paired with its embedding and producing model."""

    chunk: CodeChunk
    vector: list[float]
    model_name: str
