"""Token-counting abstractions used to enforce context budgets."""

from math import ceil
from typing import Protocol


class TokenCounter(Protocol):
    """Counts tokens for text using a model-compatible tokenizer."""

    def count(self, text: str) -> int:
        """Return the token count for ``text``."""


class ApproximateTokenCounter:
    """Dependency-free estimate based on UTF-8 byte length.

    This is a planning estimate, not an exact tokenizer. Applications should
    inject the tokenizer belonging to their selected LLM for strict limits.
    """

    def count(self, text: str) -> int:
        if not text:
            return 0
        return ceil(len(text.encode("utf-8")) / 3)
