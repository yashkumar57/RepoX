# Day 17 — Debugging Intelligence

## Goal

Introduce a repository-grounded debugging workflow for Python bug reports and tracebacks, reusing RepoX's existing retrieval, context construction, LLM adapter, and citation validation pipeline.

## Implementation

- `repox.debugging.traceback` parses standard Python traceback frame records and terminal exception details without an LLM.
- `TracebackAnalysis` preserves frames in execution order and exposes the innermost frame.
- `DebuggingService` combines the bug description with deterministic traceback facts and delegates source-grounded investigation to `RepositoryQAService`.
- `POST /repositories/{repository_id}/debug` exposes the workflow with bounded request parameters and typed response models.
- The frontend adds a **Debug an issue** workspace with description and traceback inputs, parsed frame display, investigation output, and validated source citations.
- No repository source is changed and no patch is applied automatically.

## Design decisions

1. Traceback parsing is deterministic; the model is not asked to reconstruct file paths or line numbers from raw text.
2. Debugging reuses the shared semantic retrieval, graph expansion, token-bounded context builder, interchangeable chat model, and citation validation.
3. The model prompt requires observed facts and hypotheses to be separated, likely causes to be ranked by evidence, and unsupported details to be called out.
4. Requests accept a description, traceback, or both. Empty requests are rejected.
5. Python is the only supported traceback format in this milestone. Other languages remain deferred.

## Verification

- Unit coverage for multi-frame tracebacks, exception parsing, empty input, qualified exception names, and debugging orchestration.
- API coverage for valid debugging requests and empty-request validation.
- Full backend test suite: 194 passed, 1 skipped in the packaging environment.
- Frontend dependencies are excluded from the source archive; run `pnpm exec tsc --noEmit` and `pnpm build` on the development machine.

## Known limitations

- Traceback frames are currently provided as investigation clues; retrieval still ranks source primarily through the existing semantic and graph retrieval pipeline.
- The response reports parsed traceback locations separately from model-generated diagnosis. A parsed frame is not proof that the frame contains the root cause.
- This day does not generate or apply code patches.
