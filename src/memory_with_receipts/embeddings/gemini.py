from __future__ import annotations

from google import genai
from google.genai import types

from memory_with_receipts.core.exceptions import EmbeddingError
from memory_with_receipts.embeddings.base import BaseEmbeddingProvider


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider using Google GenAI SDK and text-embedding-004 model."""

    def __init__(self, api_key: str, model_name: str = "text-embedding-004") -> None:
        self._api_key = api_key
        self._model_name = model_name
        try:
            self._client = genai.Client(api_key=api_key)
        except Exception as e:
            raise EmbeddingError(f"Failed to initialize Gemini Client: {e}") from e

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return 768

    @property
    def provider_name(self) -> str:
        return "gemini"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate document embeddings in batches of max 100."""
        if not texts:
            return []

        vectors: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            try:
                response = self._client.models.embed_content(
                    model=self.model_name,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT"
                    )
                )
                if not response.embeddings:
                    raise EmbeddingError("Gemini API returned empty embeddings.")
                vectors.extend([emb.values for emb in response.embeddings])
            except Exception as e:
                raise EmbeddingError(f"Gemini embedding generation failed: {e}") from e

        return vectors

    def embed_single(self, text: str) -> list[float]:
        """Generate a single query embedding using RETRIEVAL_QUERY task type."""
        try:
            response = self._client.models.embed_content(
                model=self.model_name,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY"
                )
            )
            if not response.embeddings:
                raise EmbeddingError("Gemini API returned empty embeddings.")
            return response.embeddings[0].values
        except Exception as e:
            raise EmbeddingError(f"Gemini embedding generation failed: {e}") from e
