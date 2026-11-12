"""Deterministic parsing for standard Python traceback text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

_FRAME_PATTERN = re.compile(
    r'^\s*File ["\'](?P<path>.+?)["\'], line (?P<line>\d+), in (?P<function>.+?)\s*$'
)
_EXCEPTION_PATTERN = re.compile(
    r"^(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt))"
    r"(?::\s*(?P<message>.*))?$"
)


def extract_exception(text: str) -> tuple[str | None, str | None]:
    """Extract a conventional exception declaration embedded in prose."""
    for line in text.splitlines():
        candidate = line.strip()
        candidate = re.sub(
            r"^(?:exception|error)\s*:\s*",
            "",
            candidate,
            flags=re.IGNORECASE,
        )
        match = _EXCEPTION_PATTERN.match(candidate)
        if match:
            return match.group("type"), match.group("message") or ""
    return None, None


@dataclass(frozen=True)
class TracebackFrame:
    """One source frame extracted from a Python traceback."""

    path: str
    line: int
    function: str

    @property
    def filename(self) -> str:
        return PurePath(self.path.replace("\\", "/")).name


@dataclass(frozen=True)
class TracebackAnalysis:
    """Normalized traceback facts; no diagnosis is inferred here."""

    frames: tuple[TracebackFrame, ...]
    exception_type: str | None
    exception_message: str | None
    raw_last_line: str | None

    @property
    def innermost_frame(self) -> TracebackFrame | None:
        return self.frames[-1] if self.frames else None


def parse_traceback(text: str) -> TracebackAnalysis:
    """Parse frame locations and the terminal exception line from traceback text."""
    frames: list[TracebackFrame] = []
    lines = text.splitlines()
    for line in lines:
        match = _FRAME_PATTERN.match(line)
        if match:
            frames.append(
                TracebackFrame(
                    path=match.group("path"),
                    line=int(match.group("line")),
                    function=match.group("function").strip(),
                )
            )

    nonempty = [line.strip() for line in lines if line.strip()]
    last_line = nonempty[-1] if nonempty else None
    exception_type = exception_message = None
    if last_line and not last_line.startswith(("File ", "Traceback ")):
        match = _EXCEPTION_PATTERN.match(last_line)
        if match:
            exception_type = match.group("type")
            exception_message = match.group("message") or ""

    return TracebackAnalysis(
        frames=tuple(frames),
        exception_type=exception_type,
        exception_message=exception_message,
        raw_last_line=last_line,
    )
