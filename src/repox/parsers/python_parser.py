"""Extract deterministic Python repository metadata using the standard AST."""

import ast
from hashlib import sha256

from repox.models.repository import (
    ClassInfo,
    FileInfo,
    FunctionInfo,
    ImportInfo,
    SourceLocation,
)


def _location(node: ast.AST) -> SourceLocation:
    """Return a one-based source range, including decorators when present."""
    start_line = getattr(node, "lineno", 1)
    decorators = getattr(node, "decorator_list", ())
    if decorators:
        start_line = min(start_line, *(decorator.lineno for decorator in decorators))

    end_line = getattr(node, "end_lineno", start_line)
    return SourceLocation(start_line=int(start_line), end_line=int(end_line))


def _segment(source: str, node: ast.AST | None) -> str:
    """Return the exact source segment for an AST node when available."""
    if node is None:
        return ""
    segment = ast.get_source_segment(source, node)
    return segment if segment is not None else ast.unparse(node)


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract parameter names in declaration order."""
    args = node.args
    parameters = [arg.arg for arg in args.posonlyargs]
    parameters.extend(arg.arg for arg in args.args)

    if args.vararg is not None:
        parameters.append(args.vararg.arg)

    parameters.extend(arg.arg for arg in args.kwonlyargs)

    if args.kwarg is not None:
        parameters.append(args.kwarg.arg)

    return parameters


def _function_expressions(
    source: str, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> tuple[list[str], list[str]]:
    """Collect calls and return expressions owned by one function scope."""
    calls: list[str] = []
    return_expressions: list[str] = []
    stack = list(reversed(node.body))

    while stack:
        current = stack.pop()

        # Nested scopes own their own calls and returns.
        if isinstance(
            current,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue

        if isinstance(current, ast.Call):
            calls.append(_segment(source, current.func))
        elif isinstance(current, ast.Return) and current.value is not None:
            return_expressions.append(_segment(source, current.value))

        stack.extend(reversed(list(ast.iter_child_nodes(current))))

    return calls, return_expressions


def _function_info(
    source: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_class: str | None = None,
    parent_scope: str | None = None,
) -> FunctionInfo:
    calls, return_expressions = _function_expressions(source, node)

    return FunctionInfo(
        name=node.name,
        parameters=_parameters(node),
        return_expressions=return_expressions,
        calls=calls,
        location=_location(node),
        parent_class=parent_class,
        docstring=ast.get_docstring(node, clean=False),
        parent_scope=parent_scope,
    )


def _collect_nested_functions(
    source: str,
    body: list[ast.stmt],
    functions: list[FunctionInfo],
    parent_scope: str,
    parent_class: str | None = None,
) -> None:
    """Collect nested functions without crossing nested class boundaries."""
    stack: list[tuple[ast.AST, str]] = [
        (child, parent_scope) for child in reversed(body)
    ]

    while stack:
        node, scope = stack.pop()

        if isinstance(node, ast.ClassDef):
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info = _function_info(
                source,
                node,
                parent_class=parent_class,
                parent_scope=scope,
            )
            functions.append(info)
            stack.extend(
                (child, f"{scope}.{info.name}") for child in reversed(node.body)
            )
            continue

        stack.extend(
            (child, scope) for child in reversed(list(ast.iter_child_nodes(node)))
        )


def _imports(module: ast.Module) -> list[ImportInfo]:
    """Extract imports and retain whether their binding is module-wide."""
    imports: list[tuple[int, int, ImportInfo]] = []

    stack: list[tuple[ast.AST, bool]] = [
        (node, False) for node in reversed(module.body)
    ]
    while stack:
        node, is_local = stack.pop()
        scope = "local" if is_local else "module"
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    (
                        node.lineno,
                        node.col_offset,
                        ImportInfo(
                            module=alias.name,
                            alias=alias.asname,
                            kind="module",
                            location=_location(node),
                            scope=scope,
                        ),
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = "." * node.level + (node.module or "")
            for alias in node.names:
                imports.append(
                    (
                        node.lineno,
                        node.col_offset,
                        ImportInfo(
                            module=module_name,
                            symbol=alias.name,
                            alias=alias.asname,
                            kind="symbol",
                            location=_location(node),
                            scope=scope,
                        ),
                    )
                )
        child_is_local = is_local or isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )
        stack.extend(
            (child, child_is_local)
            for child in reversed(list(ast.iter_child_nodes(node)))
        )

    imports.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in imports]


def _class_info(
    source: str,
    node: ast.ClassDef,
    functions: list[FunctionInfo],
) -> ClassInfo:
    """Extract a class and its directly declared methods."""
    methods: list[FunctionInfo] = []

    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method = _function_info(source, child, parent_class=node.name)
            methods.append(method)
            _collect_nested_functions(
                source,
                child.body,
                functions,
                parent_scope=f"{node.name}.{method.name}",
                parent_class=node.name,
            )

    return ClassInfo(
        name=node.name,
        methods=methods,
        location=_location(node),
        bases=[ast.unparse(base) for base in node.bases],
        docstring=ast.get_docstring(node, clean=False),
    )


def parse_python(source_code: str, path: str = "<memory>") -> FileInfo:
    """Parse Python source into RepoX's language-independent file model.

    Python's standard-library AST owns all extraction. This avoids retaining or
    dereferencing native Tree-sitter node wrappers during repository scans.
    """
    source_hash = sha256(source_code.encode("utf-8")).hexdigest()

    try:
        module = ast.parse(source_code, filename=path, type_comments=True)
    except (SyntaxError, ValueError) as exc:
        line = getattr(exc, "lineno", None)
        if line is None:
            message = f"Python syntax error: {exc}"
        else:
            message = f"Syntax error near line {line}: {exc.msg}"
        return FileInfo(
            path=path,
            language="python",
            parse_errors=[message],
            source_hash=source_hash,
        )

    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []

    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info = _function_info(source_code, node)
            functions.append(info)
            _collect_nested_functions(
                source_code,
                node.body,
                functions,
                parent_scope=info.name,
            )
        elif isinstance(node, ast.ClassDef):
            classes.append(_class_info(source_code, node, functions))

    return FileInfo(
        path=path,
        language="python",
        imports=_imports(module),
        classes=classes,
        functions=functions,
        parse_errors=[],
        source_hash=source_hash,
    )
