# ADR-002: Semantic Chunking and Initial Embedding Model

- Status: Accepted for the initial local retrieval implementation
- Date: 2026-11-08

## Context

RepoX needs to retrieve relevant source code from natural-language questions.
The retrieval layer must preserve exact source evidence and remain replaceable
without changing parsing, graph construction, or query orchestration.

## Decision

1. Create source-grounded chunks from the deterministic parser output.
2. Preserve repository-relative file paths, symbol IDs, parent symbol IDs,
   inclusive source line ranges, language, and original code.
3. Use a model-independent `EmbeddingProvider` interface.
4. Use `nomic-ai/CodeRankEmbed` as the first local embedding candidate.
5. Keep embedding dependencies optional; repository parsing and graph analysis
   must work without installing a model runtime.
6. Use the model's documented query prefix for natural-language retrieval
   queries. Code passages are embedded without that query prefix.

## Why CodeRankEmbed

The model card describes CodeRankEmbed as a 137M-parameter code-retrieval
bi-encoder with an 8,192-token context window and reports CoIR NDCG@10 of 60.1
and CodeSearchNet MRR of 77.9. The published model card identifies the model
license as MIT and provides a `sentence-transformers` integration.

This is a practical initial candidate for local experiments on an 8 GB GPU.
The published benchmark is not a guarantee of RepoX retrieval quality; RepoX
must evaluate it on its own repository-query benchmark before treating it as
the selected production model.

## Consequences

- The embedding backend can be replaced without changing `CodeChunk`.
- The model runtime is an optional dependency.
- The first model adapter uses `sentence-transformers` and requires
  `trust_remote_code=True` as shown in the model's documented usage. Before a
  production release, pin and review the exact model revision and its custom
  code rather than silently following a moving model revision.
- Inputs are checked with the model tokenizer before encoding; oversized chunks
  fail explicitly instead of being silently truncated. Tokenizer-aware splitting
  of unusually large symbols is a follow-up task.
- The vector database remains a separate decision for Day 8.

## References

- [CodeRankEmbed model card](https://huggingface.co/nomic-ai/CodeRankEmbed)
- [CoRNStack paper](https://arxiv.org/abs/2412.01007)
