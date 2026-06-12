import sys
from unittest.mock import MagicMock, patch

from memory_with_receipts.rag.cross_encoder_reranker import CrossEncoderReranker


class TestCrossEncoderReranker:
    @patch("memory_with_receipts.rag.cross_encoder_reranker.CrossEncoder")
    def test_rerank_ordering(self, mock_cross_encoder_class) -> None:
        # Mock the predict method to return controlled scores
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1, 0.9, 0.4]
        mock_cross_encoder_class.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="mock-model")
        
        results = [
            {"id": "doc1", "content": "Lowest score content"},
            {"id": "doc2", "content": "Highest score content"},
            {"id": "doc3", "content": "Medium score content"},
        ]
        
        reranked = reranker.rerank("my query", results)
        
        # Original scores: doc1: 0.1, doc2: 0.9, doc3: 0.4
        # Expected order: doc2 (0.9), doc3 (0.4), doc1 (0.1)
        assert len(reranked) == 3
        assert reranked[0]["id"] == "doc2"
        assert reranked[1]["id"] == "doc3"
        assert reranked[2]["id"] == "doc1"
        
        # Verify predict called with correct pairs
        mock_model.predict.assert_called_once_with([
            ("my query", "Lowest score content"),
            ("my query", "Highest score content"),
            ("my query", "Medium score content"),
        ])

    def test_fallback_when_import_fails(self) -> None:
        # Simulate sentence_transformers not being installed
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            reranker = CrossEncoderReranker(model_name="mock-model")
            results = [
                {"id": "doc1", "content": "Low"},
                {"id": "doc2", "content": "High"},
            ]
            # Should run without raising ImportError and return original list
            reranked = reranker.rerank("query", results)
            assert reranked == results

    @patch("memory_with_receipts.rag.cross_encoder_reranker.CrossEncoder")
    def test_fallback_on_predict_exception(self, mock_cross_encoder_class) -> None:
        mock_model = MagicMock()
        mock_model.predict.side_effect = Exception("CUDA out of memory")
        mock_cross_encoder_class.return_value = mock_model

        reranker = CrossEncoderReranker(model_name="mock-model")
        results = [{"id": "doc1", "content": "Low"}]
        
        # Should gracefully return original results instead of raising exception
        reranked = reranker.rerank("query", results)
        assert reranked == results
