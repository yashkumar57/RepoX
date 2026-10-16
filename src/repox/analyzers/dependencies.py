import ast
from pathlib import Path

from repox.models.repository import FileInfo, Relationship


def resolve_dependencies(
    root: str | Path,
    files: dict[str, FileInfo],
) -> list[Relationship]:
    """Resolve local Python imports into file-to-file relationships."""
    root = Path(root).resolve()
    # Map Python module names to repository-relative file paths.
    module_to_path = {}
    for relative_path in files:
        path = Path(relative_path)
        module = ".".join(path.with_suffix("").parts)
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        module_to_path[module] = relative_path
    relationships = []
    for relative_path, file_info in files.items():
        source_path = root / relative_path
        # Use Python's standard library to resolve relative imports.
        try:
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package_parts = list(Path(relative_path).with_suffix("").parts[:-1])
                    remove_count = max(node.level - 1, 0)
                    if remove_count:
                        package_parts = package_parts[:-remove_count]
                    base = ".".join(package_parts + ([base] if base else []))
                modules = [base] if base else []
            else:
                continue
            for module in modules:
                target = module_to_path.get(module)
                if target is None and module:
                    # Support imports from a package's __init__.py.
                    target = module_to_path.get(f"{module}.__init__")
                if target is None or target == relative_path:
                    continue
                relationships.append(
                    Relationship(
                        source=relative_path,
                        target=target,
                        kind="imports",
                        evidence=f"import {module}",
                    )
                )
    # Multiple imported symbols can refer to the same file pair.
    unique = {}
    for relationship in relationships:
        key = (relationship.source, relationship.target, relationship.kind)
        unique.setdefault(key, relationship)
    return list(unique.values())
