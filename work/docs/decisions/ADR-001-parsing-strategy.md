# ADR-001: Repository Parsing Strategy

- **Status:** Accepted — revised initial implementation
- **Original date:** 2026-10-14
- **Revision date:** 2026-11-08
- **Decision owners:** RepoX maintainers

## Context

RepoX must analyze unfamiliar repositories and extract structured information
about source files, imports, functions, classes, calls, and dependencies. The
analysis engine is intended to support Python and JavaScript/TypeScript through
a common repository model.

The initial Python implementation used Tree-sitter. During repeated repository
scans on the supported Windows development environment, accessing Tree-sitter
node text and metadata caused reproducible native access violations
(`0xC0000005`). The crash occurred inside the native binding, before Python
could raise an exception. Repeated parser changes did not make this path reliable.

## Decision

Use the parser best suited to each language while preserving the shared RepoX
models and extraction contracts:

1. **Python:** use the Python standard-library `ast` module for parsing and
   deterministic metadata extraction. It is already available, avoids native
   parser bindings, and provides source locations, syntax errors, imports,
   definitions, calls, and expressions.
2. **JavaScript/TypeScript:** evaluate Tree-sitter when those language parsers
   are implemented. Add the runtime and grammar dependencies with that work,
   rather than carrying unused native dependencies in the Python MVP.
3. **Normalization:** map language-specific parser output into RepoX's common
   repository models.
4. **Relationship analysis:** resolve imports, calls, inheritance, and
   containment from normalized facts.
5. **Intelligence:** use structured repository data and retrieved evidence to
   answer questions.

This supersedes the original decision to use Tree-sitter as the shared parsing
foundation. A common data model and analyzer pipeline remain the cross-language
abstraction; parser implementations may be language-specific.

## Consequences

### Positive

- The Python MVP no longer depends on a native parsing extension.
- Python syntax and source metadata are extracted through the standard library.
- The common repository model remains independent of parser implementation.
- Tree-sitter can be introduced alongside JavaScript/TypeScript support, where
  its multi-language grammar support provides direct value.

### Trade-offs

- Each language may use a different parser implementation.
- Python's `ast` parser rejects an invalid module as a whole; malformed files
  return a syntax diagnostic rather than partial structural extraction.
- Cross-file relationships still require additional deterministic analysis.

## Scope boundaries

The initial Python parser extracts:

- Imports, including imports inside nested scopes
- Top-level classes and functions
- Direct class methods and nested functions
- Function and method parameters
- Return expressions and call targets
- Source locations and docstrings
- Syntax diagnostics and source hashes

Full control-flow analysis, precise runtime call graphs, advanced type
resolution, and execution tracing remain outside the initial implementation.

## Validation

Automated tests cover representative Python files, nested functions, class
methods, import aliases, calls, return expressions, source locations, docstrings,
syntax errors, and repeated parsing. The parser is also exercised through a
repository-wide analysis integration check.

The decision may be revisited when JavaScript/TypeScript parsing is implemented
or when a stable, justified multi-language parsing abstraction is available.
