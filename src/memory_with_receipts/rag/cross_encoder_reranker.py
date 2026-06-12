from __future__ import annotations

import logging
from typing import TypeVar

from memory_with_receipts.rag.reranker import BaseReranker

logger = logging.getLogger(__name__)

# T represents generic search result items
T = TypeVar("T")

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None


class CrossEncoderReranker(BaseReranker):
    """Reranks search results using sentence-transformers CrossEncoder."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> None:
        self.model_name = model_name
        self._model = None
        self._failed = False

    def rerank(self, query: str, results: list[T]) -> list[T]:
        """Rerank fused search results using CrossEncoder.

        If sentence-transformers is not installed, or any error occurs,
        falls back gracefully to returning results in their original order.
        """
        if not results:
            return results

        if self._failed:
            return results

        try:
            # Lazy load the model on first call
            if self._model is None:
                if CrossEncoder is None:
                    logger.warning(
                        "sentence-transformers not installed. Reranker falling back to input order."
                    )
                    self._failed = True
                    return results
                
                self._model = CrossEncoder(self.model_name)

            # Build prediction pairs of (query, content)
            pairs: list[tuple[str, str]] = []
            for item in results:
                content = ""
                if hasattr(item, "content"):
                    content = item.content or ""
                elif isinstance(item, dict) and "content" in item:
                    content = item["content"] or ""
                pairs.append((query, content))

            scores = self._model.predict(pairs)

            # Pair up results and scores, and sort descending by score
            scored_items = list(zip(results, scores, strict=True))
            scored_items.sort(key=lambda x: x[1], reverse=True)

            return [item for item, _ in scored_items]

        except Exception as e:
            logger.error(f"Error in cross-encoder reranker: {e}. Falling back to input order.")
            self._failed = True
            return results
