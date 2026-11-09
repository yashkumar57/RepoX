"""Provider-neutral language model interface."""

from typing import Protocol


class ChatModel(Protocol):
    """Minimal interface required by RepoX question answering."""

    @property
    def model_name(self) -> str:
        """Return the configured model identifier."""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_output_tokens: int = 1_000,
    ) -> str:
        """Generate one response from system and user messages."""
