"""Local sentence-transformers embedding provider.

Uses the sentence-transformers library for local, free, reproducible embeddings.
The model is loaded lazily on first embed() call — no download at import or
construction time.

Requires optional dependency: pip install memory-with-receipts[local-embeddings]
"""

from memory_with_receipts.core.exceptions import EmbeddingError
from memory_with_receipts.embeddings.base import BaseEmbeddingProvider


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Local embedding provider using sentence-transformers.

    The model is loaded lazily: no download or GPU allocation happens until
    the first call to embed(). This allows importing the class and checking
    metadata without triggering a heavy model load.

    Args:
        model_name: HuggingFace model identifier.
            Defaults to 'all-MiniLM-L6-v2' (384-dim).
        dimension: Expected output dimension. Defaults to 384.
            Used for validation; the actual dimension comes from the model.

    Raises:
        EmbeddingError: If sentence-transformers is not installed (on first embed),
            or if the model produces vectors with unexpected dimensions.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        dimension: int = 384,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model = None  # Lazy-loaded

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "local"

    def _load_model(self) -> None:
        """Load the sentence-transformers model.

        Raises:
            EmbeddingError: If sentence-transformers is not installed.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers is not installed. "
                "Install it with: pip install memory-with-receipts[local-embeddings]"
            ) from exc

        self._model = SentenceTransformer(self._model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using the local sentence-transformers model.

        The model is loaded on first call. Subsequent calls reuse the loaded model.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            EmbeddingError: If the model is not available or produces
                unexpected dimensions.
        """
        if self._model is None:
            self._load_model()

        try:
            # encode returns numpy array, convert to list of lists
            embeddings_array = self._model.encode(texts, show_progress_bar=False)
            results = [embedding.tolist() for embedding in embeddings_array]
        except Exception as exc:
            raise EmbeddingError(
                f"Failed to generate embeddings with model '{self._model_name}': {exc}"
            ) from exc

        # Validate dimension of first result
        if results and len(results[0]) != self._dimension:
            raise EmbeddingError(
                f"Model '{self._model_name}' produced {len(results[0])}-dim vectors, "
                f"but expected {self._dimension}. Update the 'embedding_dimension' setting."
            )

        return results
