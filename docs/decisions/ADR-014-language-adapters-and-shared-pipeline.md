# ADR-014: Language Adapters and Shared Intelligence Pipeline

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

RepoX's repository scanner and analyzer directly selected the Python parser and
Python resolvers. Extending the product to additional languages would otherwise
require language-specific branches in scanning and orchestration. RepoX already
has independent `EmbeddingProvider` and `ChatModel` interfaces, so model-provider
selection does not need to be coupled to language support.

## Decision

Introduce a `LanguageAdapter` protocol and `LanguageRegistry`. Each adapter owns
source parsing, import resolution and symbol resolution, and emits RepoX's
normalized `FileInfo` and `Relationship` records. The scanner selects adapters
by file extension. The analyzer delegates language-specific resolution to the
registered adapters, then invokes the same graph builder.

Python is the first reference adapter and remains the only adapter in the default
registry for this milestone. Existing Python parser and resolver implementations
are wrapped rather than rewritten.

The shared pipeline remains responsible for semantic chunking, embedding,
vector storage, retrieval, context construction and RAG orchestration. Embedding
and chat generation remain separate provider interfaces.

## Consequences

- A future language can be added by implementing and registering an adapter,
  then satisfying shared adapter contract tests.
- The existing Python behavior and stable source identifiers are preserved.
- Language-specific resolution remains isolated because import and symbol
  semantics differ across languages.
- The current `FileInfo` model retains legacy Python-oriented metadata fields
  for compatibility. A future typed extension-metadata migration should happen
  alongside the first additional language adapter, with explicit compatibility
  tests.
