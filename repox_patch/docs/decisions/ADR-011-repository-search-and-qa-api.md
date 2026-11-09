# ADR-011: Repository Search and Q&A API

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

The Day 12 API can acquire a public GitHub repository and build its persistent
semantic index. Clients still need HTTP operations for searching indexed source
and asking repository-grounded questions.

## Decision

Expose two repository-scoped endpoints:

- `POST /repositories/{repository_id}/search`
- `POST /repositories/{repository_id}/ask`

The search endpoint delegates to the existing `SemanticSearchService` and
returns exact source chunks with paths, line ranges, symbol metadata, scores,
and distances. The Q&A endpoint delegates to the existing
`RepositoryQAService`, preserving hybrid graph retrieval, bounded context
construction, citation validation, retry, and fail-closed evidence fallback.

Query services are constructed lazily and cached per repository for the life of
the API process. The default implementation uses the repository's existing
`.repox/index` ChromaDB collection, CodeRankEmbed, and local Ollama inference.
Tests can inject a query-service factory without loading models or external
services.

If retrieval yields no evidence, Q&A returns a deterministic no-evidence
response without invoking the language model. This prevents unsupported
repository claims when the index is empty or the query has no matches.

## Consequences

- API clients can complete acquisition, indexing, semantic search, and Q&A
  through one service interface.
- Existing domain services remain the source of behavior; the API only handles
  validation, dependency construction, serialization, and HTTP error mapping.
- Model loading and vector-store initialization remain lazy.
- The default Q&A endpoint requires Ollama to be running and the configured
  model to be available.
- Query service instances are process-local. A multi-worker deployment will
  construct one cache per worker; persistent repository/index data remains on
  disk and can be reopened independently.
