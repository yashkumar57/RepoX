# ADR-013: Persistent Repository Workspace Metadata

- **Status:** Accepted
- **Date:** 2026-11-10

## Context

The Day 15 frontend initially held the active repository and indexing response only
in React state. A browser refresh therefore discarded the visible workspace even
though Git checkouts and ChromaDB vectors remained on disk. An API process restart
also discarded the in-memory indexing response.

## Decision

Use a local SQLite registry at `~/.repox/repox.sqlite3` as the durable record of
acquired repositories and their latest indexing summaries.

- Keep Git checkouts under `~/.repox/repositories/<repository_id>`.
- Keep each repository's persistent ChromaDB collection under its checkout's
  `.repox/index/` directory.
- Persist repository identity, owner, name, normalized URL, branch, and latest
  indexing response in SQLite.
- Expose `GET /repositories` and `GET /repositories/{repository_id}` for workspace
  restoration.
- Keep `POST /repositories` and `POST /repositories/{repository_id}/index` as the
  explicit acquisition and indexing operations.
- On startup, discover valid existing Git checkouts and register them. When a
  legacy ChromaDB index exists but has no SQLite report, recover its vector count
  and deterministic analysis counts without re-embedding source code.
- The frontend requests the repository list on mount and restores the most
  recently updated repository and its saved indexing response.

## Consequences

- Browser refreshes and FastAPI restarts no longer require a repository to be
  cloned or indexed again.
- Existing checkouts created before this decision are imported automatically.
- SQLite is local workspace metadata, not a replacement for ChromaDB or source
  files. The database and vector index are rebuildable local artifacts and must
  not be committed to Git.
- The API remains local-first and does not require a hosted database service.
