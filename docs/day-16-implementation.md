# Day 16: Language Adapter Boundary and Live Repository Graph

## Objective

Establish Python as RepoX's reference language implementation while keeping
language-specific syntax and resolution behind an adapter boundary. The shared
pipeline continues to consume normalized repository records.

## Delivered

- `LanguageAdapter` protocol defining parsing, import resolution and symbol
  resolution responsibilities.
- `LanguageRegistry` mapping file extensions to language adapters, with
  duplicate language/extension validation.
- `PythonLanguageAdapter` wrapping the existing standard-library AST parser and
  Python dependency/symbol resolvers.
- Scanner dispatch through the registry. Python is the only enabled adapter in
  the default registry; unsupported extensions are ignored rather than parsed as
  Python.
- Repository analysis orchestration delegates language-specific resolution to
  registered adapters and then uses the existing shared graph builder.
- Shared chunking, embedding, vector indexing, retrieval, context construction
  and RAG services remain language-neutral consumers of normalized records.
- `GET /repositories/{repository_id}/graph` returns source-located graph nodes,
  edges and aggregate metrics without loading embedding or LLM models.
- Frontend Code Graph view now fetches real repository graph data, displays
  actual node/edge relationships, source locations and composition metrics.
- Added adapter, scanner, visualization and API tests.

## Architecture boundary

Adapters own grammar and language semantics. They convert source into RepoX's
normalized `FileInfo`/`Relationship` records. Shared services operate on those
records and do not import parser implementations. The existing `FileInfo`
contract retains Python-oriented detail fields (`calls`, `bases`, and return
expressions) for compatibility with the reference implementation; future
adapters should populate the normalized common fields and use language-specific
resolver logic rather than adding language branches to shared services. A later
IR evolution can replace legacy detail fields with typed extension metadata
once additional adapters are introduced and contract-tested.

Embedding and chat generation remain separate provider abstractions:
`EmbeddingProvider` handles document/query vectors; `ChatModel` handles text
generation. Ollama and OpenAI are existing `ChatModel` adapters. New providers
should implement these contracts rather than modifying retrieval or RAG.

## Visualization contract

The graph API returns stable IDs, node kinds, repository-relative paths,
language, inclusive source line ranges, edge kinds and evidence. It intentionally
does not return layout coordinates: the frontend owns layout so alternate graph
layouts can be introduced without changing analysis semantics. Aggregate counts
are computed from the graph and parsed files, not mocked UI constants.

The current UI renders at most 24 nodes for responsiveness while the API returns
the complete graph. Searchable graph filtering and richer layouts are follow-up
work.

## Verification

- Backend regression suite: 185 passed, 1 skipped.
- Python source compilation: passed.
- TypeScript/TSX syntax transpilation: passed for 7 source files.
- Full TypeScript type-check and Next.js production build: not run in the
  packaging environment because frontend dependencies are intentionally not
  included in the source archive. Run the commands below after extracting the
  archive and using the existing frontend dependency installation.

Backend:

```powershell
python -m pytest -q
```

Frontend:

```powershell
cd frontend
pnpm exec tsc --noEmit
pnpm build
```

## Deliberate scope limits

- Python remains the only enabled language adapter in Day 16.
- No Java, C, C++, JavaScript or TypeScript parser is introduced in this
  milestone.
- No changes are made to the embedding model or LLM provider behavior.
- The visualization is based on deterministic graph data; it does not infer
  execution traces or runtime call behavior.
