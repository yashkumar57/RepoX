"""Create source-grounded chunks from deterministic repository analysis."""

from hashlib import sha256
from pathlib import Path, PurePosixPath

from repox.models.analysis import RepositoryAnalysis
from repox.models.chunk import ChunkKind, CodeChunk
from repox.models.identifiers import (
    class_node_ids,
    function_node_ids,
    function_parent_id,
)
from repox.models.repository import ClassInfo, FileInfo, FunctionInfo


def _function_qualified_name(function: FunctionInfo) -> str:
    """Mirror the graph builder's lexical naming convention."""
    if function.parent_scope:
        return f"{function.parent_scope}.{function.name}"
    if function.parent_class:
        return f"{function.parent_class}.{function.name}"
    return function.name


def _chunk_id(
    file_path: str,
    kind: ChunkKind,
    symbol_id: str,
    start_line: int,
    end_line: int,
) -> str:
    """Build a stable identifier independent of process or machine."""
    identity = f"{file_path}\0{kind}\0{symbol_id}\0{start_line}\0{end_line}"
    digest = sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"chunk:{digest}"


def _source_lines(root: Path, file_path: str) -> tuple[str, list[str]]:
    """Read a previously analyzed file using its repository-relative path."""
    relative_path = Path(*PurePosixPath(file_path).parts)
    source_path = root / relative_path
    try:
        source = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise OSError(f"Cannot read source for chunking: {file_path}: {exc}") from exc
    return source, source.splitlines()


def _source_slice(lines: list[str], start_line: int, end_line: int) -> str:
    """Extract a validated inclusive, one-based line range."""
    if (
        not isinstance(start_line, int)
        or isinstance(start_line, bool)
        or not isinstance(end_line, int)
        or isinstance(end_line, bool)
        or start_line < 1
        or end_line < start_line
        or end_line > len(lines)
    ):
        raise ValueError(
            f"Invalid source line range: {start_line!r}-{end_line!r} "
            f"for {len(lines)} lines"
        )
    return "\n".join(lines[start_line - 1 : end_line]).strip("\n")


def _make_chunk(
    *,
    file_path: str,
    language: str,
    kind: ChunkKind,
    symbol_id: str,
    symbol_name: str,
    start_line: int,
    end_line: int,
    content: str,
    parent_symbol_id: str | None,
) -> CodeChunk:
    return CodeChunk(
        id=_chunk_id(file_path, kind, symbol_id, start_line, end_line),
        file_path=file_path,
        language=language,
        kind=kind,
        symbol_id=symbol_id,
        symbol_name=symbol_name,
        start_line=start_line,
        end_line=end_line,
        content=content,
        parent_symbol_id=parent_symbol_id,
    )


def _class_chunk(
    path: str,
    file_info: FileInfo,
    class_info: ClassInfo,
    lines: list[str],
    symbol_id: str,
) -> CodeChunk | None:
    location = class_info.location
    if location is None:
        return None
    content = _source_slice(lines, location.start_line, location.end_line)
    if not content.strip():
        return None
    return _make_chunk(
        file_path=path,
        language=file_info.language,
        kind="class",
        symbol_id=symbol_id,
        symbol_name=class_info.name,
        start_line=location.start_line,
        end_line=location.end_line,
        content=content,
        parent_symbol_id=f"file:{path}",
    )


def _function_chunk(
    path: str,
    file_info: FileInfo,
    function: FunctionInfo,
    lines: list[str],
    symbol_id: str,
    parent_symbol_id: str | None,
) -> CodeChunk | None:
    location = function.location
    if location is None:
        return None
    qualified_name = _function_qualified_name(function)
    content = _source_slice(lines, location.start_line, location.end_line)
    if not content.strip():
        return None
    return _make_chunk(
        file_path=path,
        language=file_info.language,
        kind="function",
        symbol_id=symbol_id,
        symbol_name=qualified_name,
        start_line=location.start_line,
        end_line=location.end_line,
        content=content,
        parent_symbol_id=parent_symbol_id,
    )


def _module_chunks(
    path: str,
    file_info: FileInfo,
    lines: list[str],
) -> list[CodeChunk]:
    """Extract top-level code not already represented by a class/function."""
    covered = [False] * len(lines)
    top_level_functions = [
        function
        for function in file_info.functions
        if function.parent_scope is None and function.parent_class is None
    ]
    locations = [item.location for item in file_info.classes] + [
        item.location for item in top_level_functions
    ]

    for location in locations:
        if location is None:
            continue
        start = location.start_line
        end = location.end_line
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 1
            or end < start
            or end > len(lines)
        ):
            raise ValueError(
                f"Invalid source location in {path}: "
                f"{start!r}-{end!r} for {len(lines)} lines"
            )
        for line_number in range(start, end + 1):
            covered[line_number - 1] = True

    chunks = []
    index = 0
    while index < len(lines):
        if covered[index]:
            index += 1
            continue
        segment_start = index
        while index < len(lines) and not covered[index]:
            index += 1
        segment_end = index

        while segment_start < segment_end and not lines[segment_start].strip():
            segment_start += 1
        while segment_end > segment_start and not lines[segment_end - 1].strip():
            segment_end -= 1
        if segment_start == segment_end:
            continue

        start_line = segment_start + 1
        end_line = segment_end
        content = "\n".join(lines[segment_start:segment_end])
        symbol_id = f"file:{path}"
        chunks.append(
            _make_chunk(
                file_path=path,
                language=file_info.language,
                kind="module",
                symbol_id=symbol_id,
                symbol_name=path,
                start_line=start_line,
                end_line=end_line,
                content=content,
                parent_symbol_id=None,
            )
        )
    return chunks


def _chunk_file(path: str, file_info: FileInfo, root: Path) -> list[CodeChunk]:
    source, lines = _source_lines(root, path)
    if file_info.source_hash is not None:
        current_hash = sha256(source.encode("utf-8")).hexdigest()
        if current_hash != file_info.source_hash:
            raise ValueError(f"Source changed since analysis: {path}")
    chunks = _module_chunks(path, file_info, lines)
    class_ids = class_node_ids(path, file_info)
    function_ids = function_node_ids(path, file_info)

    for class_info in file_info.classes:
        chunk = _class_chunk(
            path, file_info, class_info, lines, class_ids[id(class_info)]
        )
        if chunk is not None:
            chunks.append(chunk)
        for method in class_info.methods:
            method_chunk = _function_chunk(
                path,
                file_info,
                method,
                lines,
                function_ids[id(method)],
                class_ids[id(class_info)],
            )
            if method_chunk is not None:
                chunks.append(method_chunk)

    for function in file_info.functions:
        function_chunk = _function_chunk(
            path,
            file_info,
            function,
            lines,
            function_ids[id(function)],
            function_parent_id(path, function, file_info, function_ids, class_ids),
        )
        if function_chunk is not None:
            chunks.append(function_chunk)
    return chunks


def chunk_repository(analysis: RepositoryAnalysis) -> list[CodeChunk]:
    """Chunk all successfully parsed files in a repository analysis.

    Source is read again so every chunk contains exact source text. If a file
    changed or disappeared after analysis, fail explicitly rather than return
    stale or mismatched source evidence.
    """
    chunks = []
    for path, file_info in sorted(analysis.files.items()):
        chunks.extend(_chunk_file(path, file_info, analysis.root))
    return sorted(
        chunks,
        key=lambda chunk: (
            chunk.file_path,
            chunk.start_line,
            chunk.end_line,
            chunk.kind,
            chunk.symbol_id,
        ),
    )


def subdivide_chunks(
    chunks: list[CodeChunk],
    *,
    max_tokens: int,
    count_tokens,
) -> list[CodeChunk]:
    """Split oversized source chunks at line boundaries using provider tokens."""
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")

    result: list[CodeChunk] = []
    for chunk in chunks:
        if count_tokens(chunk.embedding_text) <= max_tokens:
            result.append(chunk)
            continue

        lines = chunk.content.splitlines()
        segment: list[str] = []
        segment_start = chunk.start_line
        for offset, line in enumerate(lines):
            candidate_lines = [*segment, line]
            candidate_end = chunk.start_line + offset
            candidate = _make_chunk(
                file_path=chunk.file_path,
                language=chunk.language,
                kind=chunk.kind,
                symbol_id=chunk.symbol_id,
                symbol_name=chunk.symbol_name,
                start_line=segment_start,
                end_line=candidate_end,
                content="\n".join(candidate_lines),
                parent_symbol_id=chunk.parent_symbol_id,
            )
            if count_tokens(candidate.embedding_text) <= max_tokens:
                segment = candidate_lines
                continue
            if not segment:
                raise ValueError(
                    f"Source line {chunk.file_path}:{candidate_end} exceeds the "
                    f"embedding token limit of {max_tokens}"
                )
            result.append(
                _make_chunk(
                    file_path=chunk.file_path,
                    language=chunk.language,
                    kind=chunk.kind,
                    symbol_id=chunk.symbol_id,
                    symbol_name=chunk.symbol_name,
                    start_line=segment_start,
                    end_line=candidate_end - 1,
                    content="\n".join(segment),
                    parent_symbol_id=chunk.parent_symbol_id,
                )
            )
            single_line = _make_chunk(
                file_path=chunk.file_path,
                language=chunk.language,
                kind=chunk.kind,
                symbol_id=chunk.symbol_id,
                symbol_name=chunk.symbol_name,
                start_line=candidate_end,
                end_line=candidate_end,
                content=line,
                parent_symbol_id=chunk.parent_symbol_id,
            )
            if count_tokens(single_line.embedding_text) > max_tokens:
                raise ValueError(
                    f"Source line {chunk.file_path}:{candidate_end} exceeds the "
                    f"embedding token limit of {max_tokens}"
                )
            segment = [line]
            segment_start = candidate_end

        if segment:
            result.append(
                _make_chunk(
                    file_path=chunk.file_path,
                    language=chunk.language,
                    kind=chunk.kind,
                    symbol_id=chunk.symbol_id,
                    symbol_name=chunk.symbol_name,
                    start_line=segment_start,
                    end_line=chunk.end_line,
                    content="\n".join(segment),
                    parent_symbol_id=chunk.parent_symbol_id,
                )
            )
    return result
