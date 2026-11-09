# ADR-012: Disambiguate Duplicate Symbol Graph Identities

## Status
Accepted

## Context

A source file can legally contain multiple definitions with the same qualified
symbol name (for example, repeated method definitions in a class). The previous
graph identity used only file path and qualified name, causing distinct source
definitions to collide.

## Decision

Keep the historical graph ID for unique definitions. When a qualified name is
repeated within a file, append the definition's source range to its graph ID.
The symbol resolver and graph builder share the same identity helpers so call
relationships point to the same nodes. Ambiguous call targets remain unresolved
rather than being guessed.

## Consequences

- Duplicate definitions remain represented as separate graph nodes.
- Existing IDs for unique symbols remain backward compatible.
- Source locations make duplicate identities deterministic for a given source
  revision.
