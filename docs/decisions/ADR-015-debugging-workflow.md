# ADR-015: Repository-grounded debugging workflow

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

RepoX already provides language adapters, repository analysis, hybrid retrieval, bounded context construction, interchangeable chat models, and validated source citations. A debugging feature should reuse these systems rather than create a parallel retrieval or LLM stack.

## Decision

Add a Python traceback parser and a debugging orchestration service. The parser extracts deterministic facts (frames, paths, line numbers, function names, exception type, and message). The service turns the report and parsed facts into a focused repository question and delegates to `RepositoryQAService`. Expose the workflow through a dedicated API route and frontend workspace.

## Consequences

- Traceback facts are testable without model calls.
- Debugging inherits existing retrieval and citation safeguards.
- Model output remains an evidence-based investigation, not a guaranteed root-cause proof.
- The initial implementation is Python-specific; other language adapters can later provide equivalent diagnostic parsers.
- Patch generation and application remain out of scope.
