# ADR-009: Repository Acquisition HTTP API

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

RepoX has a GitHub acquisition service that validates and shallow-clones public
repositories into a managed workspace. The FastAPI application needs to expose
that capability without moving Git operations or repository policy into the
HTTP layer.

## Decision

Add `POST /repositories` with a Pydantic request model containing
`repository_url` and an optional `branch`.

- Return `201 Created` with repository ID, owner, name, normalized URL, branch,
  and acquisition status.
- Keep the local checkout path server-side; do not expose filesystem paths in
  the public response.
- Map invalid repository URLs and branch names to `422 Unprocessable Entity`.
- Map Git clone failures to `502 Bad Gateway`.
- Inject `GitHubRepositoryService` through the application factory to make the
  route independently testable.
- Keep API startup free of embedding model loading, vector-store initialization,
  and Ollama connections.

## Consequences

- The route is a thin HTTP adapter around the existing acquisition service.
- API tests can exercise success and failure behavior without network access.
- Acquisition is not analysis or indexing. Those operations remain separate
  lifecycle stages and will receive their own API contracts.
