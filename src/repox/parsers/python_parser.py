import tree_sitter_python
from tree_sitter import Language, Parser

from repox.models.repository import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    SourceLocation,
)

PYTHON_LANGUAGE = Language(tree_sitter_python.language())


def _text(source: bytes, node) -> str:
    """Return the source text represented by a syntax-tree node."""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _location(node) -> SourceLocation:
    """Convert Tree-sitter's zero-based rows to one-based line numbers."""
    return SourceLocation(
        start_line=node.start_point.row + 1,
        end_line=node.end_point.row + 1,
    )


def _syntax_errors(root_node) -> list[str]:
    """Collect syntax errors reported by Tree-sitter."""
    errors = []
    stack = [root_node]
    while stack:
        node = stack.pop()
        if node.type == "ERROR":
            errors.append(f"Syntax error near line {node.start_point.row + 1}")
        elif node.is_missing:
            errors.append(f"Missing {node.type} near line {node.start_point.row + 1}")
        stack.extend(reversed(node.children))
    return errors


def _parameters(source: bytes, function_node) -> list[str]:
    """Extract parameter names from a function definition."""
    parameters_node = function_node.child_by_field_name("parameters")
    if parameters_node is None:
        return []
    result = []
    for parameter in parameters_node.named_children:
        if parameter.type == "identifier":
            result.append(_text(source, parameter))
            continue
        # Handles common forms such as typed and default parameters.
        name_node = parameter.child_by_field_name("name")
        if name_node is not None:
            result.append(_text(source, name_node))
        elif parameter.named_children:
            result.append(_text(source, parameter.named_children[0]))
    return result


def _function_info(
    source: bytes,
    function_node,
    parent_class: str | None = None,
) -> FunctionInfo:
    """Extract metadata from a function or method."""
    name_node = function_node.child_by_field_name("name")
    body_node = function_node.child_by_field_name("body")
    calls = []
    return_expressions = []

    def visit(node):
        # Don't attribute a nested function's calls to its enclosing function.
        if node != function_node and node.type == "function_definition":
            return

        if node.type == "call":
            callee = node.child_by_field_name("function")
            if callee is not None:
                calls.append(_text(source, callee))

        elif node.type == "return_statement":
            if node.named_children:
                return_expressions.append(_text(source, node.named_children[-1]))

        for child in node.named_children:
            visit(child)

    if body_node is not None:
        visit(body_node)

    return FunctionInfo(
        name=_text(source, name_node),
        parameters=_parameters(source, function_node),
        return_expressions=return_expressions,
        calls=calls,
        location=_location(function_node),
        parent_class=parent_class,
    )


def _imports(source: bytes, root_node) -> list[ImportInfo]:
    """Extract basic Python import statements."""
    imports = []

    for node in root_node.named_children:
        if node.type == "import_statement":
            for child in node.named_children:
                if child.type == "aliased_import":
                    name_node = child.named_children[0]
                    alias_node = child.child_by_field_name("alias")
                    imports.append(
                        ImportInfo(
                            module=_text(source, name_node),
                            symbol=(
                                _text(source, alias_node)
                                if alias_node is not None
                                else None
                            ),
                            location=_location(child),
                        )
                    )
                else:
                    imports.append(
                        ImportInfo(
                            module=_text(source, child),
                            location=_location(child),
                        )
                    )

        elif node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            module = _text(source, module_node) if module_node is not None else ""

            for child in node.named_children:
                if child == module_node:
                    continue

                if child.type in {"dotted_name", "identifier"}:
                    imports.append(
                        ImportInfo(
                            module=module,
                            symbol=_text(source, child),
                            location=_location(node),
                        )
                    )
                elif child.type == "aliased_import":
                    name_node = child.named_children[0]
                    alias_node = child.child_by_field_name("alias")
                    imports.append(
                        ImportInfo(
                            module=module,
                            symbol=(
                                f"{_text(source, name_node)} as "
                                f"{_text(source, alias_node)}"
                                if alias_node is not None
                                else _text(source, name_node)
                            ),
                            location=_location(node),
                        )
                    )

    return imports


def parse_python(source_code: str, path: str = "<memory>") -> FileInfo:
    """Parse Python source and return RepoX's common file model."""
    source = source_code.encode("utf-8")

    parser = Parser(PYTHON_LANGUAGE)
    tree = parser.parse(source)
    root = tree.root_node
    parse_errors = _syntax_errors(root)

    classes = []
    functions = []

    for node in root.named_children:
        if node.type == "function_definition":
            functions.append(_function_info(source, node))

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            body_node = node.child_by_field_name("body")
            class_name = _text(source, name_node)
            methods = []

            if body_node is not None:
                for child in body_node.named_children:
                    if child.type == "function_definition":
                        methods.append(
                            _function_info(
                                source,
                                child,
                                parent_class=class_name,
                            )
                        )

            classes.append(
                ClassInfo(
                    name=class_name,
                    methods=methods,
                    location=_location(node),
                )
            )

    return FileInfo(
        path=path,
        language="python",
        imports=_imports(source, root),
        classes=classes,
        functions=functions,
        parse_errors=parse_errors,
    )
