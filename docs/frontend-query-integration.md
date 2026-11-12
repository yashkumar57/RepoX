# Frontend query integration

Semantic Search and Ask RepoX use the active repository ID from the restored
workspace state. They no longer display demonstration search results or a
prewritten answer.

## Semantic Search

- Sends `POST /repositories/{repository_id}/search`.
- Payload contains the current query and selected Top K value.
- Renders only source chunks returned by the API, including their repository
  relative path, line range, language, symbol, similarity score, and source.
- Supports Enter and the Search button, loading state, empty state, and API
  error state.

## Ask RepoX

- Sends `POST /repositories/{repository_id}/ask`.
- Renders the returned answer, model identifier, validated citations, and
  evidence-only fallback status.
- Supports Ctrl/Command + Enter and the Ask RepoX button, loading and error
  states.

Both requests use the shared typed API client in `frontend/lib/api.ts`. The
backend already exposes the corresponding FastAPI endpoints and caches query
services by repository ID, keeping each repository's vector index isolated.

## Manual verification

1. Start the FastAPI backend and Next.js frontend.
2. Open an indexed repository, for example `TheAlgorithms/Python`.
3. Run a search for `Dijkstra shortest path implementation using a priority
   queue`.
4. Confirm the browser Network panel shows a POST request to that repository's
   `/search` endpoint and that returned file paths belong to that repository.
5. Ask RepoX how Dijkstra's implementation works. Confirm a POST request to
   that same repository's `/ask` endpoint and inspect the returned model and
   citation metadata.
6. Switch repositories and repeat. The request URL must contain the newly
   active repository ID.
