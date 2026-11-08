"""Validate and attach embeddings to semantic code chunks."""

from collections.abc import Sequence
from math import isfinite

from repox.embeddings.base import EmbeddingProvider
from repox.models.chunk import CodeChunk, EmbeddedChunk


def embed_chunks(
    chunks: Sequence[CodeChunk],
    provider: EmbeddingProvider,
) -> list[EmbeddedChunk]:
    """Embed chunks and validate the returned vectors before persistence."""
    if not chunks:
        return []

    texts = [chunk.embedding_text for chunk in chunks]
    vectors = provider.embed_documents(texts)
    if len(vectors) != len(chunks):
        raise ValueError(
            f"Embedding provider returned {len(vectors)} vectors "
            f"for {len(chunks)} chunks"
        )

    expected_dimension: int | None = None
    embedded_chunks = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        values = [float(value) for value in vector]
        if not values:
            raise ValueError(f"Empty embedding vector for chunk {chunk.id}")
        if expected_dimension is None:
            expected_dimension = len(values)
        elif len(values) != expected_dimension:
            raise ValueError("Embedding provider returned inconsistent dimensions")
        if not all(isfinite(value) for value in values):
            raise ValueError(f"Non-finite embedding value for chunk {chunk.id}")
        embedded_chunks.append(
            EmbeddedChunk(
                chunk=chunk,
                vector=values,
                model_name=provider.model_name,
            )
        )
    return embedded_chunks
