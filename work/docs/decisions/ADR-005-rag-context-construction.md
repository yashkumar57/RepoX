# ADR-005: Bounded, source-attributed RAG context construction

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

Day 9 produces hybrid retrieval results containing semantic matches and
structural graph neighbors. Passing every result directly to a language model
would create uncontrolled prompt sizes and lose the distinction between direct
semantic evidence and graph-derived context.

## Decision

Add a provider-neutral context layer between retrieval and LLM integration:

1. `RAGContextBuilder` prioritizes semantic matches by descending score.
2. Structural results follow in a deterministic relationship-priority order.
3. Each source retains its chunk ID, path, symbol, inclusive line range, exact
   content, semantic score (when present), graph relationships, and evidence.
4. A configurable token budget is enforced against the rendered context.
5. Chunks are included whole or omitted; source text is not silently truncated.
6. `PromptBuilder` creates separate system and user messages and instructs the
   model to ground claims in evidence and cite exact source locations.
7. A `TokenCounter` protocol allows an application to inject its model's exact
   tokenizer. The built-in counter is explicitly an estimate.

## Consequences

- Context selection is deterministic and testable without an LLM provider.
- Retrieval remains independent of prompt format and tokenization.
- Source attribution and retrieval provenance survive prompt assembly.
- The approximate default counter cannot guarantee a provider's exact context
  window; production adapters should supply the model-specific tokenizer and
  reserve additional capacity for generated output and provider framing.
- Whole-chunk selection can omit a large chunk even when truncating it might
  have allowed partial evidence. This is intentional to preserve source fidelity.

## Alternatives considered

- **Pass all retrieval results:** rejected because prompt size is unbounded.
- **Silently truncate source chunks:** rejected because truncation can remove
  syntax, definitions, or line context and would make attribution misleading.
- **Hard-code a tokenizer dependency:** rejected to keep the core context layer
  model-independent and avoid adding a model SDK before Day 11.
