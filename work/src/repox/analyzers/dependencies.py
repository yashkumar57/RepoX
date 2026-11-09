import ast
from pathlib import Path

from repox.models.repository import FileInfo, Relationship


def _module_parts(relative_path: str) -> list[str]:
    """Convert a repository path into importable Python module parts."""
    path = Path(relative_path)
    parts = list(path.with_suffix("").parts)

    # In the conventional src layout, src is a source root,
    # not part of the Python import path.
    if parts and parts[0] == "src":
        parts = parts[1:]

    if parts and parts[-1] == "__init__":
        parts.pop()

    return parts


def _module_index(files: dict[str, FileInfo]) -> dict[str, str]:
    """Map importable module names to repository-relative file paths."""
    modules: dict[str, str] = {}

    for relative_path in sorted(files):
        module_parts = _module_parts(relative_path)
        module = ".".join(module_parts)

        if module:
            modules[module] = relative_path

    return modules


def _resolve_module(
    module: str,
    modules: dict[str, str],
) -> str | None:
    """Resolve a module name to a repository file, if present."""
    if module in modules:
        return modules[module]

    return modules.get(f"{module}.__init__")


def _relative_module(
    relative_path: str,
    node: ast.ImportFrom,
) -> str | None:
    """Convert a relative import into its absolute module name."""
    if node.level == 0:
        return node.module or ""

    parts = _module_parts(relative_path)

    # Remove the current module name to obtain its containing package.
    package_parts = parts[:-1]

    # level=1 means current package; level=2 means parent package.
    remove_count = node.level - 1

    if remove_count:
        if remove_count >= len(package_parts):
            return None

        package_parts = package_parts[:-remove_count]

    if node.module:
        package_parts.extend(node.module.split("."))

    return ".".join(package_parts)


def resolve_dependencies(
    root: str | Path,
    files: dict[str, FileInfo],
) -> list[Relationship]:
    """Resolve local Python imports into file-to-file relationships."""
    root = Path(root).resolve()
    modules = _module_index(files)
    relationships: list[Relationship] = []

    for relative_path in sorted(files):
        source_path = root / relative_path

        try:
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            targets: list[tuple[str, str]] = []

            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _resolve_module(alias.name, modules)

                    if target:
                        targets.append((target, alias.name))

            elif isinstance(node, ast.ImportFrom):
                base = _relative_module(relative_path, node)

                if base is None:
                    continue

                base_target = _resolve_module(base, modules)

                if base_target:
                    targets.append((base_target, base))

                # `from package import routes` may refer to a local
                # submodule rather than a symbol in __init__.py.
                for alias in node.names:
                    if alias.name == "*":
                        continue

                    candidate = f"{base}.{alias.name}" if base else alias.name
                    submodule_target = _resolve_module(candidate, modules)

                    if submodule_target:
                        targets.append((submodule_target, candidate))

            for target, imported_module in targets:
                if target == relative_path:
                    continue

                relationships.append(
                    Relationship(
                        source=relative_path,
                        target=target,
                        kind="imports",
                        evidence=f"import {imported_module}",
                    )
                )

    # Keep one edge per source file, target file, and relationship kind.
    unique: dict[tuple[str, str, str], Relationship] = {}

    for relationship in relationships:
        key = (
            relationship.source,
            relationship.target,
            relationship.kind,
        )
        unique.setdefault(key, relationship)

    return list(unique.values())
