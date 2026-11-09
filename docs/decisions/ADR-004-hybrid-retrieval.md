# ADR-004: Hybrid Semantic and Structural Retrieval

- Status: Accepted for the initial repository-grounded retrieval layer
- Date: 2026-11-09

## Context

Day 8 provides persistent nearest-neighbor search over source-grounded code
chunks. Semantic similarity is useful for finding code from natural-language
questions, but a similar function in isolation may not explain how a feature
flows through the repository. RepoX already has a deterministic graph of
files, symbols, imports, calls, containment, and inheritance.

## Decision

1. Keep vector search responsible for selecting the primary semantic matches.
2. Expand each primary match by one graph hop using the deterministic
   repository graph.
3. Include source chunks for callers, callees, parents, children, imports,
   dependents, base classes, and subclasses when a corresponding source chunk
   exists.
4. Preserve exact source content, repository-relative paths, and inclusive
   source line ranges from `CodeChunk`.
5. Keep semantic similarity scores only on direct vector-search matches.
   Structural context is explicitly labeled and is not assigned a fabricated
   similarity score.
6. Deduplicate chunks reached through multiple paths while merging their
   relationship labels, related seed symbols, and graph-edge evidence.
7. Keep the semantic result limit (`top_k`) separate from the structural
   context limit (`context_limit`).

## Consequences

- Retrieval results provide both conceptually relevant code and its immediate
  deterministic relationships.
- The LLM-facing layer can distinguish semantic evidence from graph-derived
  context.
- Structural expansion is bounded to one hop and a configurable context count;
  multi-hop traversal and query-intent-aware expansion remain future work.
- Graph quality is limited by the current parser and relationship resolvers.
  Unresolved runtime behavior must not be presented as a discovered fact.
