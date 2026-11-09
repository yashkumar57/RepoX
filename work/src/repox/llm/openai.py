"""OpenAI chat-completions adapter, loaded only when explicitly used."""

from typing import Any


class OpenAIChatModel:
    """ChatModel adapter using the OpenAI Python SDK.

    The SDK is an optional dependency. API credentials are read by the SDK
    from ``OPENAI_API_KEY`` unless an injected client is supplied.
    """

    def __init__(self, model: str = "gpt-4o-mini", client: Any | None = None) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "OpenAI support requires the optional 'llm' extra; "
                    "install it with: python -m pip install -e '.[llm]'"
                ) from exc
            client = OpenAI()
        self._client = client
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_output_tokens: int = 1_000,
    ) -> str:
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_output_tokens,
            temperature=0,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("The language model returned an empty response")
        return content.strip()
