"""Stable graph identities for repository definitions."""

from collections import Counter

from repox.models.repository import FileInfo, FunctionInfo


def _suffix(location, ordinal: int) -> str:
    if location is not None:
        return f"@{location.start_line}:{location.end_line}"
    return f"@{ordinal}"


def function_node_ids(path: str, file_info: FileInfo) -> dict[int, str]:
    """Return IDs for every function/method, disambiguating duplicate names.

    Unique definitions retain the historical ID format. Duplicate qualified
    names include source ranges, preserving each definition independently.
    """
    entries: list[tuple[FunctionInfo, str]] = []
    for function in file_info.functions:
        entries.append((function, _qualified_function_name(function)))
    for class_info in file_info.classes:
        for method in class_info.methods:
            entries.append((method, f"{class_info.name}.{method.name}"))

    counts = Counter(name for _, name in entries)
    ordinals: Counter[str] = Counter()
    result: dict[int, str] = {}
    for function, name in entries:
        ordinals[name] += 1
        identity = f"function:{path}:{name}"
        if counts[name] > 1:
            identity += _suffix(function.location, ordinals[name])
        result[id(function)] = identity
    return result


def class_node_ids(path: str, file_info: FileInfo) -> dict[int, str]:
    """Return class IDs, disambiguating repeated class declarations."""
    counts = Counter(item.name for item in file_info.classes)
    ordinals: Counter[str] = Counter()
    result: dict[int, str] = {}
    for class_info in file_info.classes:
        ordinals[class_info.name] += 1
        identity = f"class:{path}:{class_info.name}"
        if counts[class_info.name] > 1:
            identity += _suffix(class_info.location, ordinals[class_info.name])
        result[id(class_info)] = identity
    return result


def function_parent_id(
    path: str,
    function: FunctionInfo,
    file_info: FileInfo,
    function_ids: dict[int, str],
    class_ids: dict[int, str],
) -> str | None:
    """Return a function's canonical lexical parent ID, if it is known.

    Location containment distinguishes repeated lexical names. An unresolved
    parent returns ``None`` so callers never fabricate an ID without a node.
    """
    if function.parent_scope:
        candidates = [
            candidate
            for candidate in _all_functions(file_info)
            if _qualified_function_name(candidate) == function.parent_scope
            and candidate.location is not None
            and function.location is not None
            and candidate.location.start_line <= function.location.start_line
            and candidate.location.end_line >= function.location.end_line
        ]
        if len(candidates) == 1:
            return function_ids[id(candidates[0])]

        matching = [
            candidate
            for candidate in _all_functions(file_info)
            if _qualified_function_name(candidate) == function.parent_scope
        ]
        return function_ids[id(matching[0])] if len(matching) == 1 else None

    if function.parent_class:
        candidates = [
            item for item in file_info.classes if item.name == function.parent_class
        ]
        return class_ids[id(candidates[0])] if len(candidates) == 1 else None

    return f"file:{path}"


def _all_functions(file_info: FileInfo) -> list[FunctionInfo]:
    functions = list(file_info.functions)
    for class_info in file_info.classes:
        functions.extend(class_info.methods)
    return functions


def _qualified_function_name(function: FunctionInfo) -> str:
    if function.parent_scope:
        return f"{function.parent_scope}.{function.name}"
    if function.parent_class:
        return f"{function.parent_class}.{function.name}"
    return function.name
