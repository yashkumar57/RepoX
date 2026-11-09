# ADR-010: Repository analysis and indexing API

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

RepoX can acquire a public GitHub repository through `POST /repositories`, and
its deterministic analyzer and incremental semantic indexer are already
available as independent Python services. The API needs a controlled way to
connect these layers without loading the embedding model during application
startup or exposing managed filesystem paths.

## Decision

Add `POST /repositories/{repository_id}/index`.

1. Resolve the repository ID within the configured managed workspace. IDs must
   be 32-character lowercase hexadecimal identifiers, and resolved paths must
   remain direct children of that workspace.
2. Reconstruct checkout metadata from the clone's Git origin and current branch,
   so repositories remain addressable after an API process restart.
3. Run deterministic repository analysis before semantic indexing.
4. Use the existing `RepositoryIndexer` and its incremental hash/reuse/delete
   behavior. Keep the ChromaDB collection inside the checkout at `.repox/index/`.
5. Load the local CodeRankEmbed provider only when indexing is first requested.
   Reuse that provider within the API process; create one repository-scoped
   vector store and indexing service per repository.
6. Allow an indexing-service factory to be injected for tests and alternate
   deployments. API startup remains independent of model and vector-store
   initialization.

## HTTP behavior

- `200 OK`: analysis and index synchronization completed; response reports file,
  relationship, chunk, embedding, reuse, and deletion counts.
- `404 Not Found`: repository ID is malformed, unknown, or absent from the
  managed workspace.
- `422 Unprocessable Content`: analysis/index validation rejected the request,
  including unsafe synchronization when repository scanning has errors.
- `503 Service Unavailable`: optional embedding or vector-store dependencies are
  not installed.

## Consequences

- Acquisition and indexing remain separate operations with explicit lifecycle
  boundaries.
- The API does not expose local checkout paths.
- Re-indexing is incremental and uses the existing deterministic chunk identity
  and content-hash rules.
- The embedding model is loaded on demand, not at API startup.
- The current API process caches indexing services and a shared embedding
  provider. A process restart reconstructs repository metadata and reopens the
  persistent vector store; it does not require recloning the repository.
- This endpoint is synchronous. Long-running/background job orchestration is a
  separate concern and is not introduced in this step.
