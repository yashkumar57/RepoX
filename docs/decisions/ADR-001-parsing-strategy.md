# ADR-001: Repository Parsing Strategy

- **Status:** Accepted — initial implementation
- **Date:** 2026-10-14
- **Decision owners:** RepoX maintainers

## Context

RepoX must analyze unfamiliar repositories and extract structured information about source files, imports, functions, classes, calls, and dependencies.

The analysis engine must support Python and JavaScript/TypeScript initially, with the ability to add languages without redesigning the entire system.

## Options considered

### Option A: Python `ast`

Use Python's built-in Abstract Syntax Tree module.

- Advantages: No additional dependency, mature parser, strong Python syntax support.
- Disadvantages: Python-specific; other languages require different parsing implementations.

### Option B: Tree-sitter

Use Tree-sitter to parse supported programming languages into syntax trees.

- Advantages: Multi-language support, consistent parsing foundation, useful source locations.
- Disadvantages: Language grammars and queries require additional configuration; parsing alone does not resolve every semantic relationship.

### Option C: Hybrid parsing architecture

Use Tree-sitter as the shared parsing foundation, with language-specific analyzers and a common repository model.

- Advantages: Consistent architecture, extensibility, and room for language-specific analysis.
- Disadvantages: More initial setup and abstraction than a single-language parser.

## Decision

RepoX will adopt **Option C: a hybrid parsing architecture based on Tree-sitter**.

The initial implementation will target Python. JavaScript and TypeScript support will follow through the same common model.

The architecture will separate:

1. **Parsing:** Convert source code into syntax trees.
2. **Extraction:** Identify files, imports, classes, functions, parameters, calls, and source locations.
3. **Normalization:** Convert extracted information into RepoX's common repository model.
4. **Relationship analysis:** Build dependency and containment relationships.
5. **Intelligence:** Use structured repository data and retrieved evidence to answer questions.

## Consequences

### Positive

- New language support can reuse the shared analysis pipeline.
- Parser output can be tested independently of AI features.
- Dependency analysis and visualization can consume a consistent data model.
- Language-specific details can be retained where necessary.

### Trade-offs

- Tree-sitter does not automatically resolve every import or determine every runtime behavior.
- Cross-file relationships will require additional analysis.
- The initial abstraction must remain small to avoid premature complexity.

## Scope boundaries

The initial parser will extract:

- Source file paths and language
- Imports
- Classes and functions
- Function and method parameters
- Return expressions
- Function and method calls
- Source locations
- Basic containment relationships

Full control-flow analysis, precise runtime call graphs, advanced type resolution, and execution tracing are outside this initial implementation.

## Validation

The decision will be evaluated using automated tests covering:

- Correct extraction from representative Python files
- Nested functions and class methods
- Import and call relationships
- Syntax errors and unsupported constructs
- Stable output through the common repository model

The decision may be revisited if Tree-sitter creates unnecessary complexity or fails to meet the MVP's requirements.