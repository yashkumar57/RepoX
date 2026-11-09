# ADR-007: Local-first LLM inference with Ollama

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

RepoX should be usable by developers without paid API access, API credentials,
or a hosted inference account. The repository analysis, embedding, vector
indexing, and retrieval layers already run locally. The LLM integration should
follow the same local-first principle while preserving the provider-neutral
`ChatModel` interface.

## Decision

Add `OllamaChatModel`, an adapter for Ollama's local `/api/chat` HTTP endpoint.
The adapter uses Python's standard library, so it adds no Python dependency and
requires no API key. Its default model identifier is `qwen2.5-coder:3b`; users
can select another model through the constructor. The server address can be
configured with `OLLAMA_HOST` or the constructor's `host` argument.

Keep `OpenAIChatModel` as an optional adapter for developers who explicitly
choose a hosted provider. The `RepositoryQAService`, retrieval, context
construction, and citation-validation layers remain provider-neutral and are
not changed by this decision.

Ollama is a separate local runtime that users install and run. The model is
downloaded separately with Ollama. Local inference can use CPU and, when
supported by the installed runtime and model, GPU acceleration. Performance
and the practical model size depend on each developer's hardware.

## Consequences

- The default LLM path does not require a paid API or API key.
- The Ollama adapter adds no Python package dependency.
- Unit tests can validate the HTTP contract without a running Ollama server.
- A separate local smoke test is still required to verify a real model and
  runtime installation.
- Developers can choose a smaller model for constrained hardware or a larger
  model when their hardware supports it.
- Repository analysis and retrieval remain usable when Ollama is unavailable;
  only LLM-backed operations require the local model server.
- The default model is a convenience, not a hardware guarantee. Users can
  override it with any model available in their Ollama installation.
