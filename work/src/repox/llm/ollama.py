"""Local Ollama chat adapter implemented with the Python standard library."""

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaChatModel:
    """ChatModel adapter for a locally running Ollama server.

    No Python SDK or API key is required. Ollama serves its local HTTP API by
    default at ``http://localhost:11434``. The host can be overridden with the
    ``OLLAMA_HOST`` environment variable or the ``host`` constructor argument.
    """

    def __init__(
        self,
        model: str = "qwen2.5-coder:3b",
        *,
        host: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        configured_host = host or os.environ.get(
            "OLLAMA_HOST", "http://localhost:11434"
        )
        configured_host = configured_host.strip().rstrip("/")
        if not configured_host.startswith(("http://", "https://")):
            raise ValueError("Ollama host must start with http:// or https://")

        self._model = model
        self._host = configured_host
        self._timeout = timeout

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
        """Generate a non-streaming response through Ollama's chat endpoint."""
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": max_output_tokens,
            },
        }
        request = Request(
            f"{self._host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout) as response:
                result: Any = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            message = f"Ollama returned HTTP {exc.code}"
            if detail:
                message = f"{message}: {detail}"
            raise RuntimeError(message) from exc
        except URLError as exc:
            raise RuntimeError(
                "Could not connect to Ollama. Start Ollama and verify that "
                f"it is listening at {self._host}."
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Ollama returned an invalid JSON response") from exc

        if not isinstance(result, dict):
            raise RuntimeError("Ollama returned an unexpected response format")

        message = result.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            detail = result.get("error")
            if isinstance(detail, str) and detail.strip():
                raise RuntimeError(f"Ollama generation failed: {detail}")
            raise RuntimeError("Ollama returned an empty response")
        return content.strip()
