"""Embedding providers for vector generation.

Pluggable providers: mock (tests), local (sentence-transformers), future API providers.
"""

from memory_with_receipts.embeddings.base import BaseEmbeddingProvider
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider

__all__ = ["BaseEmbeddingProvider", "MockEmbeddingProvider"]
