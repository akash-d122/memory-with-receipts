"""Reranker interface and NoOp default implementation.

The reranker sits after RRF fusion and before final result construction.
Phase 4 ships with NoOpReranker. Phase 7 will add a real cross-encoder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

T = TypeVar("T")


class BaseReranker(ABC):
    """Abstract base for rerankers."""

    @abstractmethod
    def rerank(self, query: str, results: list[T]) -> list[T]:
        """Rerank search results based on the query.

        Args:
            query: The original search query text.
            results: Fused search results to rerank.

        Returns:
            Reranked results (same items, possibly different order).
        """


class NoOpReranker(BaseReranker):
    """Pass-through reranker that returns results unchanged.

    Extension point for Phase 7 cross-encoder reranking.
    """

    def rerank(self, query: str, results: list[T]) -> list[T]:
        """Return results without modification."""
        return results
