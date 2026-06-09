"""Unit tests for reranker interface and NoOpReranker."""

from memory_with_receipts.rag.reranker import NoOpReranker


class TestNoOpReranker:
    """Tests for the NoOp pass-through reranker."""

    def test_returns_results_unchanged(self) -> None:
        """NoOpReranker must return results without modification."""
        reranker = NoOpReranker()
        items = [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.5}]
        result = reranker.rerank("test query", items)
        assert result == items

    def test_preserves_order(self) -> None:
        """NoOpReranker must preserve the original ordering."""
        reranker = NoOpReranker()
        items = ["c", "a", "b"]
        result = reranker.rerank("query", items)
        assert result == ["c", "a", "b"]

    def test_empty_results(self) -> None:
        """NoOpReranker handles empty input."""
        reranker = NoOpReranker()
        result = reranker.rerank("query", [])
        assert result == []

    def test_returns_same_object(self) -> None:
        """NoOpReranker returns the same list object (no copy)."""
        reranker = NoOpReranker()
        items = [1, 2, 3]
        result = reranker.rerank("query", items)
        assert result is items
