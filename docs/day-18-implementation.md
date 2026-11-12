# Day 18 — Traceback-to-Source Evidence Resolution

## Goal

Make Python debugging evidence more precise before asking the language model to
explain a failure. Day 18 strengthens the boundary between deterministic facts,
indexed source, and model-generated hypotheses.

## Implementation

- Traceback paths are normalized consistently across slash styles and relative
  path prefixes.
- Exact path matches are preferred. Checkout-root-independent suffix matches
  are accepted only when they resolve to one unique file in the indexed repo.
- Ambiguous paths (for example, two packages containing `auth.py`) fail closed
  instead of selecting arbitrary source.
- A traceback frame is mapped to the narrowest enclosing source chunk, preferring
  the function-level chunk over overlapping class/module chunks.
- Retrieval evidence records the exact traceback line that selected the chunk.
- Debugging instructions explicitly distinguish the failing attribute receiver
  from the function's return value. A `NoneType` attribute error proves that the
  receiver at that operation was `None`; it does not prove that the current
  function returned `None`.
- No-evidence diagnosis avoids recommending a default identity/username as an
  authentication fallback and avoids attributing a `None` value to an unobserved
  helper function.

## Verification

- Unit tests cover unique suffix mapping, narrowest-function selection, and
  ambiguous-path rejection.
- Existing Day 17 tests remain in place as regression coverage.

## Scope

Python remains the only supported debugging language. No automatic source edits
or patches are applied. Model output remains advisory; repository citations are
still validated against the exact context supplied to the model.
