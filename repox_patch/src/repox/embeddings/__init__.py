"""Embedding providers and chunk embedding utilities."""

from repox.embeddings.base import EmbeddingProvider
from repox.embeddings.code_rank import CodeRankEmbedder
from repox.embeddings.service import embed_chunks

__all__ = ["CodeRankEmbedder", "EmbeddingProvider", "embed_chunks"]
