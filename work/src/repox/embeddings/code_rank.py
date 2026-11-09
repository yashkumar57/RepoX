"""Local CodeRankEmbed provider backed by sentence-transformers."""

from collections.abc import Sequence
from typing import Any

MODEL_NAME = "nomic-ai/CodeRankEmbed"
QUERY_PREFIX = "Represent this query for searching relevant code: "


def _as_list(value: Any) -> list:
    """Convert NumPy-like arrays or ordinary sequences into Python lists."""
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


class CodeRankEmbedder:
    """Generate local code-search embeddings with Nomic CodeRankEmbed.

    The model is loaded lazily when this class is instantiated. Install the
    optional dependency with ``pip install -e ".[embeddings]"`` first.
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        device: str | None = None,
        batch_size: int = 16,
        normalize_embeddings: bool = True,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "CodeRankEmbed requires the optional embedding dependencies. "
                'Install them with: python -m pip install -e ".[embeddings]"'
            ) from exc

        model_kwargs = {"trust_remote_code": True}
        if device is not None:
            model_kwargs["device"] = device
        self._model = SentenceTransformer(model_name, **model_kwargs)
        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.dimension = self._model.get_embedding_dimension()
        self.max_seq_length = self._model.max_seq_length

    def _validate_input_lengths(self, texts: Sequence[str]) -> None:
        """Reject inputs that would be silently truncated by the model."""
        transformer = self._model[0]
        tokenizer = transformer.tokenizer
        for batch_start in range(0, len(texts), self.batch_size):
            batch = list(texts[batch_start : batch_start + self.batch_size])
            encoded = tokenizer(batch, padding=False, truncation=False)
            lengths = [len(token_ids) for token_ids in encoded["input_ids"]]
            for offset, token_count in enumerate(lengths):
                if token_count > self.max_seq_length:
                    index = batch_start + offset
                    raise ValueError(
                        f"Embedding input {index} has {token_count} tokens; "
                        f"the model limit is {self.max_seq_length}. Split the "
                        "source chunk before embedding."
                    )

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed source chunks as retrieval passages."""
        if not texts:
            return []
        self._validate_input_lengths(texts)
        vectors = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in _as_list(vectors)]

    def embed_query(self, query: str) -> list[float]:
        """Embed a natural-language query using CodeRankEmbed's required prefix."""
        if not query.strip():
            raise ValueError("query must not be empty")
        prefixed_query = QUERY_PREFIX + query.strip()
        self._validate_input_lengths([prefixed_query])
        vector = self._model.encode(
            prefixed_query,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        return [float(value) for value in _as_list(vector)]
