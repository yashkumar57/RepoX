"""Resolve function calls and class inheritance across a repository."""

from collections import defaultdict
from pathlib import PurePosixPath

from repox.models.repository import (
    FileInfo,
    FunctionInfo,
    Relationship,
)


def _function_id(path: str, name: str) -> str:
    return f"function:{path}:{name}"


def _class_id(path: str, name: str) -> str:
    return f"class:{path}:{name}"


def _qualified_function_name(function: FunctionInfo) -> str:
    """Build the qualified name of a function or method."""
    if function.parent_scope:
        return f"{function.parent_scope}.{function.name}"

    if function.parent_class:
        return f"{function.parent_class}.{function.name}"

    return function.name


def _build_symbol_index(files: dict[str, FileInfo]):
    """Index functions and classes by name and source file."""
    functions_by_name = defaultdict(list)
    functions_by_file = defaultdict(list)
    classes_by_name = defaultdict(list)
    classes_by_file = defaultdict(list)

    for path, file_info in files.items():
        for function in file_info.functions:
            name = _qualified_function_name(function)
            functions_by_name[function.name].append((path, name, function))
            functions_by_file[path].append((name, function))

        for class_info in file_info.classes:
            classes_by_name[class_info.name].append((path, class_info))
            classes_by_file[path].append(class_info)

            for method in class_info.methods:
                name = f"{class_info.name}.{method.name}"
                functions_by_name[method.name].append((path, name, method))
                functions_by_file[path].append((name, method))

    return (
        functions_by_name,
        functions_by_file,
        classes_by_name,
        classes_by_file,
    )


def _imported_symbols(
    file_info: FileInfo,
) -> dict[str, list[tuple[str, str]]]:
    """Map local symbol names to their original module and symbol."""
    imported = defaultdict(list)

    for item in file_info.imports:
        if item.kind != "symbol" or not item.symbol:
            continue

        local_name = item.alias or item.symbol

        imported[local_name].append((item.module, item.symbol))

    return dict(imported)


def _imported_modules(
    file_info: FileInfo,
) -> dict[str, list[str]]:
    """Map locally visible module names to their original module paths."""
    imported = defaultdict(list)

    for item in file_info.imports:
        if item.kind != "module":
            continue

        # Without an alias, Python binds `import package.submodule`
        # to the top-level name `package`.
        local_name = item.alias or item.module.split(".")[0]

        imported[local_name].append(item.module)

    return dict(imported)


def _resolve_import_module(
    module: str,
    current_path: str,
    files: dict[str, FileInfo],
) -> str | None:
    """Resolve an absolute or relative module name to a repository file."""
    level = len(module) - len(module.lstrip("."))
    module_name = module[level:]
    module_parts = module_name.split(".") if module_name else []

    if level:
        current_parts = list(PurePosixPath(current_path).with_suffix("").parts)

        if current_parts and current_parts[-1] == "__init__":
            current_parts.pop()
        else:
            current_parts = current_parts[:-1]

        # Remove the conventional src directory from the import path.
        if current_parts and current_parts[0] == "src":
            current_parts = current_parts[1:]

        remove_count = level - 1

        if remove_count >= len(current_parts):
            return None

        if remove_count:
            current_parts = current_parts[:-remove_count]

        module_parts = current_parts + module_parts

    if not module_parts:
        return None

    module_path = "/".join(module_parts)

    candidates = [
        f"{module_path}.py",
        f"{module_path}/__init__.py",
        f"src/{module_path}.py",
        f"src/{module_path}/__init__.py",
    ]

    for candidate in candidates:
        if candidate in files:
            return candidate

    return None


def _resolve_imported_qualified_name(
    name: str,
    current_path: str,
    files: dict[str, FileInfo],
    imported_modules: dict[str, list[str]],
) -> tuple[str, str] | None:
    """Resolve a qualified name accessed through an imported module."""
    parts = name.split(".")

    if len(parts) < 2:
        return None

    local_module_name = parts[0]
    module_candidates = imported_modules.get(local_module_name, [])

    if len(module_candidates) != 1:
        return None

    original_module = module_candidates[0]
    original_parts = original_module.split(".")

    remaining_parts = parts[1:]

    # Handle `import package.submodule` where Python binds `package`,
    # but the imported module path includes `submodule`.
    if (
        len(original_parts) > 1
        and original_parts[0] == local_module_name
        and remaining_parts[: len(original_parts) - 1] == original_parts[1:]
    ):
        remaining_parts = remaining_parts[len(original_parts) - 1 :]

    # Initial scope: resolve a single function or class after the module.
    if len(remaining_parts) != 1:
        return None

    target_path = _resolve_import_module(
        original_module,
        current_path,
        files,
    )

    if target_path is None:
        return None

    return target_path, remaining_parts[0]


def _resolve_function(
    name: str,
    current_path: str,
    files: dict[str, FileInfo],
    functions_by_name,
    imported_symbols: dict[str, list[tuple[str, str]]],
    imported_modules: dict[str, list[str]],
):
    """Resolve a function call only when its target is unambiguous."""

    # Resolve calls such as helpers.calculate() or h.calculate().
    if "." in name:
        imported_target = _resolve_imported_qualified_name(
            name,
            current_path,
            files,
            imported_modules,
        )

        if imported_target is None:
            return None

        target_path, target_name = imported_target

        candidates = [
            entry
            for entry in functions_by_name.get(target_name, [])
            if entry[0] == target_path
            and entry[2].parent_class is None
            and entry[2].parent_scope is None
        ]

        return candidates[0] if len(candidates) == 1 else None

    # Resolve calls imported using `from module import function`.
    if name in imported_symbols:
        imported = imported_symbols[name]

        if len(imported) != 1:
            return None

        module, original_name = imported[0]
        target_path = _resolve_import_module(module, current_path, files)

        if target_path is None:
            return None

        candidates = [
            entry
            for entry in functions_by_name.get(original_name, [])
            if entry[0] == target_path
            and entry[2].parent_class is None
            and entry[2].parent_scope is None
        ]

        return candidates[0] if len(candidates) == 1 else None

    # Resolve unqualified calls only when globally unambiguous.
    candidates = [
        entry
        for entry in functions_by_name.get(name, [])
        if entry[2].parent_class is None and entry[2].parent_scope is None
    ]

    if len(candidates) != 1:
        return None

    return candidates[0]


def _resolve_base_class(
    base: str,
    current_path: str,
    files: dict[str, FileInfo],
    classes_by_name,
    imported_symbols: dict[str, list[tuple[str, str]]],
    imported_modules: dict[str, list[str]],
):
    """Resolve a class base when exactly one target is identifiable."""

    # Resolve qualified bases such as models.BaseModel.
    if "." in base:
        imported_target = _resolve_imported_qualified_name(
            base,
            current_path,
            files,
            imported_modules,
        )

        if imported_target is None:
            return None

        target_path, target_name = imported_target

        candidates = [
            entry
            for entry in classes_by_name.get(target_name, [])
            if entry[0] == target_path
        ]

        return candidates[0] if len(candidates) == 1 else None

    # Resolve bases imported using `from module import BaseClass`.
    if base in imported_symbols:
        imported = imported_symbols[base]

        if len(imported) != 1:
            return None

        module, original_name = imported[0]
        target_path = _resolve_import_module(module, current_path, files)

        if target_path is None:
            return None

        candidates = [
            entry
            for entry in classes_by_name.get(original_name, [])
            if entry[0] == target_path
        ]

        return candidates[0] if len(candidates) == 1 else None

    # Resolve classes declared in the same file.
    local_candidates = [
        entry for entry in classes_by_name.get(base, []) if entry[0] == current_path
    ]

    return local_candidates[0] if len(local_candidates) == 1 else None


def resolve_symbols(files: dict[str, FileInfo]) -> list[Relationship]:
    """Resolve identifiable function calls and class inheritance."""
    (
        functions_by_name,
        _,
        classes_by_name,
        _,
    ) = _build_symbol_index(files)

    relationships = []
    seen = set()

    for path, file_info in files.items():
        imported_symbols = _imported_symbols(file_info)
        imported_modules = _imported_modules(file_info)

        functions = list(file_info.functions)

        for class_info in file_info.classes:
            functions.extend(class_info.methods)

        for function in functions:
            source_name = _qualified_function_name(function)
            source_id = _function_id(path, source_name)

            for call in function.calls:
                target = _resolve_function(
                    call,
                    path,
                    files,
                    functions_by_name,
                    imported_symbols,
                    imported_modules,
                )

                if target is None:
                    continue

                target_path, target_name, _ = target
                target_id = _function_id(target_path, target_name)

                key = (source_id, target_id, "calls")

                if key not in seen:
                    seen.add(key)
                    relationships.append(
                        Relationship(
                            source=source_id,
                            target=target_id,
                            kind="calls",
                            evidence=call,
                        )
                    )

        for class_info in file_info.classes:
            source_id = _class_id(path, class_info.name)

            for base in class_info.bases:
                target = _resolve_base_class(
                    base,
                    path,
                    files,
                    classes_by_name,
                    imported_symbols,
                    imported_modules,
                )

                if target is None:
                    continue

                target_path, target_class = target
                target_id = _class_id(target_path, target_class.name)

                key = (source_id, target_id, "inherits")

                if key not in seen:
                    seen.add(key)
                    relationships.append(
                        Relationship(
                            source=source_id,
                            target=target_id,
                            kind="inherits",
                            evidence=base,
                        )
                    )

    return relationships
