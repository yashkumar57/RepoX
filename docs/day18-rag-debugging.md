# Day 18 — RAG and debugging investigation improvements

## Problems observed in manual validation

- Debug reports with no traceback, or with traceback paths outside the active checkout, stopped at symptom-only diagnosis. This prevented RepoX from using the repository to identify relevant implementations worth inspecting.
- The debugging flow could lose the full bug report and traceback facts when a semantic retrieval override supplied a shorter query to the RAG context builder.
- Ask RepoX frequently fell back to raw evidence excerpts when the local model omitted or malformed citations.
- Ask RepoX rendered Markdown as literal text, making headings, lists, inline code, and code examples difficult to read.
- Semantic search used a click-only action rather than a native form submission, making Enter-key submission and browser form behavior inconsistent.

## Changes

### Debugging retrieval

1. Exact traceback-to-source mapping remains the highest-confidence path.
2. If a traceback frame cannot be mapped, RepoX now performs semantic retrieval using the bug description, exception type/message, and frame function names.
3. If no traceback is supplied, RepoX also performs semantic retrieval from the bug description.
4. Retrieved chunks in these fallback paths are explicitly labelled as related candidates, not verified failing lines. The full bug report and traceback facts remain in the RAG prompt.
5. If no relevant candidates are retrieved, RepoX retains symptom-level diagnosis and does not manufacture source citations.

### Citation prompting

- Clarified the exact citation syntax expected from the model: `[relative/path.py:12-24]`.
- Added an explicit example and prohibited code-formatted citations, shortened ranges, and unsupported claims.
- Kept citation validation and the evidence-only fallback as fail-closed safeguards.

### Frontend

- Ask RepoX now renders Markdown headings, paragraphs, ordered/unordered lists, inline code, and fenced code blocks using escaped HTML.
- Semantic search now uses a native form submit handler, supporting both the Search button and Enter key.
- Search and Ask screens are keyed to the active repository so prior repository state cannot be reused after a repository switch.

## Validation

- Backend tests: `202 passed, 1 skipped` in the build environment.
- Frontend TSX syntax transpilation: passed.
- Full Next.js type-check/build and Ruff checks still need to be run in the user's Windows development environment because the build container does not have the frontend dependencies or Ruff installed.

## Known limitation

A traceback whose paths do not exist in the active repository cannot be treated as an exact source match. RepoX now searches for related candidate code, but only an exact mapped frame or directly supporting source can justify a claim about the failing line.
