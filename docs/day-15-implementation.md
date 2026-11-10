# Day 15: Frontend ↔ Backend Integration

## Delivered

- Typed TypeScript API client with environment-configured FastAPI base URL.
- GitHub repository acquisition through `POST /repositories`.
- Repository indexing through `POST /repositories/{repository_id}/index`.
- Real indexing metrics and frontend loading/error states.
- Local SQLite persistence for repository metadata and indexing summaries.
- `GET /repositories` and `GET /repositories/{repository_id}` for workspace restoration.
- Startup discovery of pre-existing managed Git checkouts.
- Recovery of legacy Chroma index counts and deterministic analysis metrics without re-embedding.
- Frontend restoration of the most recently updated repository after refresh.
- CORS support for local Next.js development origins.

## Persistent storage

- Repository registry: `~/.repox/repox.sqlite3`.
- Git checkouts: `~/.repox/repositories/<repository_id>/`.
- Vector index: `<checkout>/.repox/index/`.

The registry is deliberately outside the project checkout. It is local application
state and must not be committed to the RepoX source repository.

## Verification

- Backend test suite: 182 passed.
- Python source compilation: passed.
- TypeScript check (`pnpm exec tsc --noEmit`): passed.
- Next.js production build (`pnpm build`): passed.
- Browser refresh persistence: passed.
- FastAPI restart persistence: passed.

A ChromaDB telemetry dependency emits one deprecation warning during tests.
