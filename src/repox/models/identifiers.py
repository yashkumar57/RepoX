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


def _qualified_function_name(function: FunctionInfo) -> str:
    if function.parent_scope:
        return f"{function.parent_scope}.{function.name}"
    if function.parent_class:
        return f"{function.parent_class}.{function.name}"
    return function.name
