"""Abstract base class for embedding providers.

Every embedding provider must implement:
- model_name: identifier of the embedding model
- dimension: output vector dimension
- provider_name: human-readable provider label (e.g. "local", "mock", "openai")
- embed(texts): batch embedding of multiple texts

The base class provides:
- embed_single(text): convenience wrapper around embed()
- validate_dimension(vector): raises EmbeddingError if vector length != dimension
"""

from abc import ABC, abstractmethod

from memory_with_receipts.core.exceptions import EmbeddingError


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the embedding model (e.g. 'all-MiniLM-L6-v2')."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Output vector dimension (e.g. 384)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider label (e.g. 'local', 'mock', 'openai')."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors, one per input text.
            Each vector has length == self.dimension.

        Raises:
            EmbeddingError: If embedding generation fails.
        """

    def embed_single(self, text: str) -> list[float]:
        """Generate an embedding for a single text.

        Convenience wrapper around embed() for single-text use cases.

        Args:
            text: The string to embed.

        Returns:
            A single embedding vector of length self.dimension.
        """
        results = self.embed([text])
        return results[0]

    def validate_dimension(self, vector: list[float]) -> None:
        """Validate that a vector has the expected dimension.

        Args:
            vector: The embedding vector to validate.

        Raises:
            EmbeddingError: If len(vector) != self.dimension.
        """
        if len(vector) != self.dimension:
            raise EmbeddingError(
                f"Embedding dimension mismatch: expected {self.dimension}, "
                f"got {len(vector)}. Model: {self.model_name}, "
                f"provider: {self.provider_name}"
            )
