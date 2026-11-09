# ADR-008: GitHub Repository Acquisition Boundary

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

The product requirements specify that a developer supplies a public GitHub
repository URL. RepoX's existing scanner and analysis pipeline operate on a local
repository directory. Repository transport therefore needs a distinct boundary
before analysis begins.

## Decision

Introduce `GitHubRepositoryService` under `repox.ingestion`.

The service:

- accepts HTTPS URLs whose host is exactly `github.com`;
- accepts only the repository root URL (`owner/repository`), with an optional
  `.git` suffix;
- rejects credentials, custom ports, query strings, fragments, and escaped paths;
- optionally checks out a requested branch;
- performs a shallow, single-branch clone using an argument list (never a shell);
- writes each checkout into a unique directory under a RepoX-managed workspace;
- enforces a configurable clone timeout and removes partial checkouts on failure;
- returns immutable checkout metadata, including the local path.

The default workspace is `~/.repox/repositories`. Callers can inject a different
workspace for tests or deployment configuration.

## Consequences

- The scanner, parser, graph builder, indexer, and query services remain unaware
  of GitHub transport.
- API handlers can orchestrate acquisition and analysis without duplicating core
  logic.
- Only public HTTPS GitHub repositories are supported by this initial adapter.
- Clone size is not yet capped; timeout is the current execution bound. A future
  deployment may add repository-size and concurrency limits.
