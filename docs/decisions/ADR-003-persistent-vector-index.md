# ADR-003: Persistent Local Vector Index

- Status: Accepted for the initial semantic retrieval implementation
- Date: 2026-11-08

## Context

Day 7 introduced model-independent code embeddings. RepoX now needs durable
nearest-neighbor retrieval without making parsing, chunking, or embedding
providers depend on a particular vector database. The initial experience must
work on a developer's laptop without a hosted database account.

## Decision

1. Define a `VectorStore` protocol for collection configuration, existing
   content-hash lookup, upsert, deletion, and nearest-neighbor query.
2. Implement the first adapter with ChromaDB's persistent local client.
3. Store the index under `.repox/index/` by default and exclude `.repox/` from
   version control. The original repository files remain the source of truth.
4. Scope the default Chroma collection to a repository identity so unrelated
   repositories do not share retrieval results.
5. Use cosine distance and persist source content plus scalar source metadata
   alongside each vector.
6. Persist the embedding model name and vector dimension at collection level;
   reject incompatible model/dimension changes rather than mix vectors.
7. Compute a SHA-256 hash of each chunk's exact embedding input (metadata plus source content). Reuse vectors
   whose chunk ID and embedding-input hash are unchanged; re-embed changed chunks and
   delete IDs no longer present after successful embedding/upsert.
8. Abort a full synchronization when scanning reports unreadable files. An
   unreadable file must not be interpreted as a deleted file and pruned.
9. Keep ChromaDB optional. Deterministic analysis remains usable without the
   vector-store extra installed.

## Consequences

- A fresh clone creates its own local index; no remote database or credentials
  are required.
- Re-indexing an unchanged repository avoids model inference for existing
  chunks.
- The vector index is a rebuildable cache, not authoritative repository data.
- Switching embedding models requires a fresh collection or a deliberate index
  rebuild.
- ChromaDB can later be replaced by another adapter implementing `VectorStore`.
- The first implementation synchronizes one repository collection per store;
  concurrent writers and transactional multi-process coordination are not yet
  supported.
