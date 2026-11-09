# ADR-006: Provider-neutral LLM-powered repository Q&A

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

Days 9 and 10 provide hybrid repository retrieval and token-bounded, source-
attributed prompt construction. The next layer must generate an answer without
coupling core RepoX behavior to one model vendor. Model output also cannot be
assumed to contain valid source references merely because the prompt requests
them.

## Decision

Introduce a `ChatModel` protocol with a single `generate` operation and a
provider-specific `OpenAIChatModel` adapter in an optional `llm` dependency
extra. `RepositoryQAService` orchestrates retrieval, context building, prompt
assembly, generation, and citation validation. The answer model retains the
original RAG context for inspection and debugging.

Citations use `[repository/relative/path.py:start-end]` syntax. Evidence
headers provide an exact, ready-to-copy citation. A citation is accepted only
when its path exists in the context supplied to the model and its inclusive
line range falls within one of those source chunks. Invalid citations are
surfaced separately rather than silently trusted. If the first answer has no
accepted citations or contains invalid citations, the service makes one
citation-repair generation attempt. It keeps the repaired answer only if its
validation result improves; it never creates citations itself.

## Consequences

- Core installation does not require an LLM SDK or API key.
- Other hosted or local models can implement `ChatModel` without changing the
  question-answering pipeline.
- Provider calls occur only when the application invokes the QA service.
- Tests can exercise orchestration deterministically with a fake model.
- Citation validation confirms source-location membership, not semantic truth.
- A single repair attempt can improve citation compliance, but a model may still
  return an uncited answer; the structured result exposes this rather than
  pretending the answer is grounded.
- Token budgeting for the context remains an estimate unless the caller injects
  the selected model's exact tokenizer.
