from __future__ import annotations

from google import genai
from google.genai import types

from memory_with_receipts.core.exceptions import EmbeddingError
from memory_with_receipts.embeddings.base import BaseEmbeddingProvider


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider using Google GenAI SDK and Gemini embedding models."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "text-embedding-004",
        dimension: int = 768,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._dimension = dimension
        try:
            self._client = genai.Client(api_key=api_key)
        except Exception as e:
            raise EmbeddingError(f"Failed to initialize Gemini Client: {e}") from e

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "gemini"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate document embeddings in batches of max 100 with automatic retry."""
        if not texts:
            return []

        vectors: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            content_batch = [types.Content(parts=[types.Part.from_text(text=t)]) for t in batch]

            max_retries = 5
            base_delay = 5.0
            response = None

            for attempt in range(max_retries):
                try:
                    response = self._client.models.embed_content(
                        model=self.model_name,
                        contents=content_batch,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=self.dimension,
                        )
                    )
                    break
                except Exception as e:
                    err_str = str(e)
                    is_rate_limit = (
                        "429" in err_str or
                        "RESOURCE_EXHAUSTED" in err_str or
                        "quota" in err_str.lower() or
                        "limit" in err_str.lower()
                    )
                    if is_rate_limit and attempt < max_retries - 1:
                        import time
                        sleep_time = base_delay * (2 ** attempt)
                        print(
                            f"\n      [RATE LIMIT] Rate limit hit. "
                            f"Retrying in {sleep_time:.1f}s "
                            f"(attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(sleep_time)
                    else:
                        raise EmbeddingError(f"Gemini embedding generation failed: {e}") from e

            if not response or not response.embeddings:
                raise EmbeddingError("Gemini API returned empty embeddings.")
            vectors.extend([emb.values for emb in response.embeddings])

        return vectors

    def embed_single(self, text: str) -> list[float]:
        """Generate a single query embedding with automatic retry."""
        max_retries = 5
        base_delay = 5.0

        for attempt in range(max_retries):
            try:
                response = self._client.models.embed_content(
                    model=self.model_name,
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY",
                        output_dimensionality=self.dimension,
                    )
                )
                if not response.embeddings:
                    raise EmbeddingError("Gemini API returned empty embeddings.")
                return response.embeddings[0].values
            except Exception as e:
                err_str = str(e)
                is_rate_limit = (
                    "429" in err_str or
                    "RESOURCE_EXHAUSTED" in err_str or
                    "quota" in err_str.lower() or
                    "limit" in err_str.lower()
                )
                if is_rate_limit and attempt < max_retries - 1:
                    import time
                    sleep_time = base_delay * (2 ** attempt)
                    time.sleep(sleep_time)
                else:
                    raise EmbeddingError(f"Gemini embedding generation failed: {e}") from e
