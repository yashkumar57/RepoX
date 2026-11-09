"""Natural-language semantic retrieval over a persistent vector store."""

from math import isfinite

from repox.embeddings.base import EmbeddingProvider
from repox.models.chunk import CodeChunk
from repox.models.search import SearchResult
from repox.vector_store.base import VectorStore


class SemanticSearchService:
    """Embed user queries and resolve nearest vectors to source-grounded chunks."""

    def __init__(self, store: VectorStore, provider: EmbeddingProvider) -> None:
        self.store = store
        self.provider = provider

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Return the most similar code chunks with cosine similarity scores."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        vector = [float(value) for value in self.provider.embed_query(query)]
        if not vector or not all(isfinite(value) for value in vector):
            raise ValueError("query embedding must contain finite values")
        self.store.configure(self.provider.model_name, len(vector))
        matches = self.store.query(vector, top_k)

        results = []
        for match in matches:
            metadata = match.metadata
            chunk = CodeChunk(
                id=match.id,
                file_path=str(metadata["file_path"]),
                language=str(metadata["language"]),
                kind=str(metadata["kind"]),  # type: ignore[arg-type]
                symbol_id=str(metadata["symbol_id"]),
                symbol_name=str(metadata["symbol_name"]),
                start_line=int(metadata["start_line"]),
                end_line=int(metadata["end_line"]),
                content=match.document,
                parent_symbol_id=str(metadata.get("parent_symbol_id") or "") or None,
            )
            results.append(
                SearchResult(
                    chunk=chunk,
                    distance=match.distance,
                    score=1.0 - match.distance,
                )
            )
        return results
