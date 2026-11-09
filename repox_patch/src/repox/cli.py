"""Command-line interface for repository analysis."""

import argparse
from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository


def _mermaid_label(node) -> str:
    """Create a readable Mermaid label for a graph node."""
    if node.kind == "file":
        label = node.path
    elif node.kind == "class":
        label = f"class {node.name} ({node.path})"
    else:
        qualified_name = node.id.split(":", 2)[-1]
        label = f"function {qualified_name}() ({node.path})"

    return label.replace('"', "#quot;").replace("\n", "<br/>")


def _print_mermaid(graph) -> None:
    """Print the repository graph in Mermaid flowchart syntax."""
    print("flowchart LR")

    node_ids = {
        node_id: f"node_{index}" for index, node_id in enumerate(sorted(graph.nodes))
    }

    for node_id in sorted(graph.nodes):
        node = graph.nodes[node_id]
        mermaid_id = node_ids[node_id]
        label = _mermaid_label(node)
        print(f'    {mermaid_id}["{label}"]')

    for edge in graph.edges:
        source = node_ids[edge.source]
        target = node_ids[edge.target]
        print(f"    {source} -->|{edge.kind}| {target}")


def main(argv: list[str] | None = None) -> None:
    """Analyze a repository and display its structure."""
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
    analysis = analyze_repository(root)

    if args.format == "mermaid":
        _print_mermaid(analysis.graph)

        if analysis.scan_errors:
            print()
            print("%% Scan warnings:")
            for error in analysis.scan_errors:
                print(f"%% {error.path}: {error.message}")

        return

    files = analysis.files
    import_relationships = analysis.import_relationships
    symbol_relationships = analysis.symbol_relationships
    graph = analysis.graph

    function_count = sum(
        len(file.functions) + sum(len(cls.methods) for cls in file.classes)
        for file in files.values()
    )
    class_count = sum(len(file.classes) for file in files.values())
    import_count = sum(len(file.imports) for file in files.values())

    print(f"Repository: {root}")
    print(f"Python files: {len(files)}")
    print(f"Files that could not be read: {len(analysis.scan_errors)}")
    print(f"Classes: {class_count}")
    print(f"Functions and methods: {function_count}")
    print(f"Import statements/symbols detected: {import_count}")
    print(f"Local file dependencies: {len(import_relationships)}")
    print(f"Resolved symbol relationships: {len(symbol_relationships)}")
    print(f"Graph nodes: {len(graph.nodes)}")
    print(f"Graph edges: {len(graph.edges)}")
    print(f"Graph validation errors: {len(analysis.validation_errors)}")

    error_count = sum(len(file.parse_errors) for file in files.values())
    files_with_errors_count = sum(bool(file.parse_errors) for file in files.values())
    print(f"Files with parse errors: {files_with_errors_count}")
    print(f"Parse errors detected: {error_count}")

    print()
    print("Files:")
    for path in sorted(files):
        print(f"  - {path}")

    print("\nDependencies:")
    if not import_relationships:
        print("  No local file dependencies resolved.")
    else:
        for relationship in import_relationships:
            print(f"  {relationship.source} -> {relationship.target}")

    if symbol_relationships:
        print("\nResolved symbol relationships:")
        for relationship in symbol_relationships:
            print(
                f"  {relationship.source} -> {relationship.target} "
                f"({relationship.kind})"
            )

    files_with_errors = [file for file in files.values() if file.parse_errors]
    if files_with_errors:
        print("\nParse errors:")
        for file in files_with_errors:
            for error in file.parse_errors:
                print(f"  {file.path}: {error}")

    if analysis.scan_errors:
        print("\nScan errors:")
        for error in analysis.scan_errors:
            print(f"  {error.path}: {error.message}")

    if analysis.validation_errors:
        print("\nGraph validation errors:")
        for error in analysis.validation_errors:
            print(f"  {error}")


if __name__ == "__main__":
    main()
