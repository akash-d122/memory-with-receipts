"""Deterministic mock embedding provider for unit tests.

Produces reproducible vectors by hashing input text, so the same string always
yields the same embedding. Vectors are normalized to unit length. No external
dependencies required.
"""

import hashlib
import math
import struct

from memory_with_receipts.embeddings.base import BaseEmbeddingProvider


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider for testing.

    Generates reproducible, normalized vectors from a hash of the input text.
    No model download or GPU required.

    Args:
        dimension: Output vector dimension. Defaults to 384.
        model_name_override: Override the model name reported by the provider.
    """

    def __init__(
        self,
        dimension: int = 384,
        model_name_override: str = "mock-embedding-model",
    ) -> None:
        self._dimension = dimension
        self._model_name = model_name_override

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "mock"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic embeddings by hashing each text.

        The algorithm:
        1. SHA-256 hash the text to get a seed
        2. Use the seed to generate dimension floats via iterative hashing
        3. Normalize the resulting vector to unit length

        Args:
            texts: List of strings to embed.

        Returns:
            List of normalized embedding vectors.
        """
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        """Generate a single deterministic, normalized vector from text."""
        # Hash the text to get a reproducible seed
        digest = hashlib.sha256(text.encode("utf-8")).digest()

        # Generate raw floats by iteratively hashing
        raw = []
        current = digest
        while len(raw) < self._dimension:
            # Each SHA-256 gives 32 bytes = 8 floats (4 bytes each)
            current = hashlib.sha256(current).digest()
            # Unpack 8 floats from 32 bytes, convert to [-1, 1] range
            for i in range(0, 32, 4):
                if len(raw) >= self._dimension:
                    break
                # Interpret 4 bytes as unsigned int, map to [-1, 1]
                value = struct.unpack(">I", current[i : i + 4])[0]
                raw.append((value / (2**32 - 1)) * 2 - 1)

        # Normalize to unit length
        magnitude = math.sqrt(sum(x * x for x in raw))
        if magnitude == 0:
            # Edge case: return zero vector (should not happen with SHA-256)
            return raw
        return [x / magnitude for x in raw]
