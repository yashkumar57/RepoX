"""Persistent local ChromaDB adapter."""

from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from repox.models.chunk import EmbeddedChunk
from repox.vector_store.base import StoredVector


class ChromaVectorStore:
    """Store RepoX vectors in a local, persistent ChromaDB collection.

    ChromaDB is imported lazily, so users who only use deterministic analysis do
    not need the optional vector-store dependency installed.
    """

    def __init__(
        self,
        persist_directory: str | Path,
        collection_name: str = "repox",
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise ImportError(
                "Persistent semantic indexing requires ChromaDB. Install it with: "
                'python -m pip install -e ".[vector-store]"'
            ) from exc

        self.persist_directory = Path(persist_directory).expanduser().resolve()
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=str(self.persist_directory))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "repox_schema_version": 1},
        )

    @classmethod
    def for_repository(
        cls,
        repository_root: str | Path,
        index_directory: str | Path | None = None,
    ) -> "ChromaVectorStore":
        """Create a repository-scoped store under ``.repox/index`` by default."""
        root = Path(repository_root).expanduser().resolve()
        storage_path = (
            Path(index_directory).expanduser().resolve()
            if index_directory is not None
            else root / ".repox" / "index"
        )
        identity = sha256(str(root).casefold().encode("utf-8")).hexdigest()[:16]
        return cls(storage_path, collection_name=f"repo_{identity}")

    def configure(self, model_name: str, dimension: int | None = None) -> None:
        """Prevent incompatible embedding models or dimensions being mixed."""
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if dimension is not None and dimension < 1:
            raise ValueError("embedding dimension must be positive")

        metadata = dict(self._collection.metadata or {})
        stored_model = metadata.get("embedding_model")
        stored_dimension = metadata.get("embedding_dimension")
        if stored_model is not None and stored_model != model_name:
            raise ValueError(
                "The existing ChromaDB collection uses embedding model "
                f"{stored_model!r}, not {model_name!r}. Use a fresh collection or "
                "clear and rebuild the index before switching models."
            )
        if (
            dimension is not None
            and stored_dimension is not None
            and int(stored_dimension) != dimension
        ):
            raise ValueError(
                "The existing ChromaDB collection uses embedding dimension "
                f"{stored_dimension}, not {dimension}. Rebuild the index."
            )

        # ChromaDB treats ``hnsw:space`` as an immutable collection
        # configuration value. It is accepted when the collection is created,
        # but passing it back to Collection.modify() raises ValueError even
        # when the value is unchanged. Keep it out of metadata updates; the
        # cosine distance configuration remains attached to the collection.
        updated = dict(metadata)
        updated.pop("hnsw:space", None)
        updated["embedding_model"] = model_name
        if dimension is not None:
            updated["embedding_dimension"] = dimension
        if updated != metadata:
            self._collection.modify(metadata=updated)

    def get_chunk_hashes(self) -> dict[str, str]:
        """Read chunk IDs and hashes without loading source documents or vectors."""
        result: dict[str, str] = {}
        offset = 0
        batch_size = 500
        while True:
            page = self._collection.get(
                include=["metadatas"], limit=batch_size, offset=offset
            )
            ids = page.get("ids", [])
            metadatas = page.get("metadatas") or []
            for chunk_id, metadata in zip(ids, metadatas, strict=True):
                content_hash = metadata.get("content_hash")
                if isinstance(content_hash, str):
                    result[chunk_id] = content_hash
            if len(ids) < batch_size:
                break
            offset += len(ids)
        return result

    def upsert(
        self,
        chunks: Sequence[EmbeddedChunk],
        content_hashes: Mapping[str, str],
    ) -> None:
        """Persist source documents, vectors and searchable scalar metadata."""
        if not chunks:
            return
        model_names = {item.model_name for item in chunks}
        dimensions = {len(item.vector) for item in chunks}
        if len(model_names) != 1 or len(dimensions) != 1:
            raise ValueError(
                "A ChromaDB upsert must use one model and vector dimension"
            )
        model_name = next(iter(model_names))
        dimension = next(iter(dimensions))
        self.configure(model_name, dimension)

        metadatas = []
        for item in chunks:
            chunk = item.chunk
            content_hash = content_hashes.get(chunk.id)
            if content_hash is None:
                raise ValueError(f"Missing content hash for chunk {chunk.id}")
            metadatas.append(
                {
                    "file_path": chunk.file_path,
                    "language": chunk.language,
                    "kind": chunk.kind,
                    "symbol_id": chunk.symbol_id,
                    "symbol_name": chunk.symbol_name,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "parent_symbol_id": chunk.parent_symbol_id or "",
                    "content_hash": content_hash,
                    "model_name": item.model_name,
                }
            )

        self._collection.upsert(
            ids=[item.chunk.id for item in chunks],
            embeddings=[item.vector for item in chunks],
            documents=[item.chunk.content for item in chunks],
            metadatas=metadatas,
        )

    def delete(self, chunk_ids: Sequence[str]) -> None:
        """Remove obsolete records; empty deletes are a no-op."""
        if chunk_ids:
            self._collection.delete(ids=list(chunk_ids))

    def query(self, vector: Sequence[float], limit: int) -> list[StoredVector]:
        """Query ChromaDB using cosine distance."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not vector:
            raise ValueError("query vector must not be empty")
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[[float(value) for value in vector]],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            StoredVector(
                id=chunk_id,
                document=document or "",
                metadata=metadata or {},
                distance=float(distance),
            )
            for chunk_id, document, metadata, distance in zip(
                ids, documents, metadatas, distances, strict=True
            )
        ]
