import argparse
from pathlib import Path

from repox.analyzers.dependencies import resolve_dependencies
from repox.scanner import scan_repository


def main(argv: list[str] | None = None) -> None:
    """Scan a repository and display its structure."""
    parser = argparse.ArgumentParser(
        prog="repox",
        description="Analyze a repository's Python structure and dependencies.",
    )
    parser.add_argument("root", help="Path to the repository to analyze")
    parser.add_argument(
        "--format",
        choices=["text", "mermaid"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    files = scan_repository(root)
    relationships = resolve_dependencies(root, files)
    if args.format == "mermaid":
        print("flowchart LR")
        node_ids = {path: f"file_{index}" for index, path in enumerate(sorted(files))}
        for path, node_id in node_ids.items():
            print(f'    {node_id}["{path}"]')
        for relationship in relationships:
            source = node_ids.get(relationship.source)
            target = node_ids.get(relationship.target)
            if source and target:
                print(f"    {source} --> {target}")
        return
    function_count = sum(
        len(file.functions) + sum(len(cls.methods) for cls in file.classes)
        for file in files.values()
    )
    class_count = sum(len(file.classes) for file in files.values())
    import_count = sum(len(file.imports) for file in files.values())
    print(f"Repository: {root}")
    print(f"Python files: {len(files)}")
    print(f"Classes: {class_count}")
    print(f"Functions and methods: {function_count}")
    print(f"Import statements/symbols detected: {import_count}")
    print(f"Local file dependencies: {len(relationships)}")
    error_count = sum(len(file.parse_errors) for file in files.values())
    files_with_errors_count = sum(bool(file.parse_errors) for file in files.values())
    print(f"Files with parse errors: {files_with_errors_count}")
    print(f"Parse errors detected: {error_count}")
    print()
    print("Files:")
    for path in sorted(files):
        print(f"  - {path}")
    print("\nDependencies:")
    if not relationships:
        print("  No local file dependencies resolved.")
    else:
        for relationship in relationships:
            print(f"  {relationship.source} -> {relationship.target}")
    files_with_errors = [file for file in files.values() if file.parse_errors]
    if files_with_errors:
        print("\nParse errors:")
        for file in files_with_errors:
            for error in file.parse_errors:
                print(f"  {file.path}: {error}")
