"""Gemini LLM provider using the google-genai SDK.

This module is guarded with a helpful ImportError if the optional
dependency group [llm-gemini] is not installed:

    uv pip install "memory-with-receipts[llm-gemini]"

GeminiLLMProvider is never called in automated tests — it requires a
real API key.  Tests use MockLLMProvider instead.
"""

from __future__ import annotations

from memory_with_receipts.core.exceptions import GenerationError
from memory_with_receipts.llm.base import BaseLLMProvider, GenerationResult


class GeminiLLMProvider(BaseLLMProvider):
    """LLM provider backed by Google Gemini via google-genai SDK.

    Args:
        api_key: Gemini API key.  If empty, raises GenerationError on first call.
        model_name: Gemini model identifier (default: ``gemini-3.5-flash``).
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.5-flash",
    ) -> None:
        try:
            from google import genai  # type: ignore[import]
            from google.genai import types  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "google-genai is not installed. "
                "Install the optional dependency group: "
                "uv pip install 'memory-with-receipts[llm-gemini]'"
            ) from exc

        if not api_key:
            raise GenerationError("Gemini API key must be non-empty.")

        self._client = genai.Client(api_key=api_key)
        self._types = types
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(self, prompt: str) -> GenerationResult:
        """Send prompt to Gemini and return a GenerationResult.

        Raises:
            GenerationError: On any SDK or network error.
        """
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
            )
            answer = response.text
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", None)
            output_tokens = getattr(usage, "candidates_token_count", None)
        except Exception as exc:
            raise GenerationError(f"Gemini generation failed: {exc}") from exc

        return GenerationResult(
            answer=answer,
            raw_prompt=prompt,
            model=self.model_name,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
