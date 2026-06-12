from unittest.mock import MagicMock, patch

import pytest

from memory_with_receipts.core.exceptions import EmbeddingError
from memory_with_receipts.embeddings.gemini import GeminiEmbeddingProvider


class TestGeminiEmbeddingProvider:
    @patch("memory_with_receipts.embeddings.gemini.genai.Client")
    def test_provider_properties(self, mock_client_class) -> None:
        provider = GeminiEmbeddingProvider(api_key="mock-key")
        assert provider.model_name == "text-embedding-004"
        assert provider.dimension == 768
        assert provider.provider_name == "gemini"

    @patch("memory_with_receipts.embeddings.gemini.genai.Client")
    def test_embed_batching_and_task_type(self, mock_client_class) -> None:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Setup mock responses for two batches (150 texts total, batched by 100)
        mock_emb_1 = MagicMock()
        mock_emb_1.values = [0.1] * 768
        
        mock_response_1 = MagicMock()
        mock_response_1.embeddings = [mock_emb_1] * 100
        
        mock_response_2 = MagicMock()
        mock_response_2.embeddings = [mock_emb_1] * 50
        
        mock_client.models.embed_content.side_effect = [mock_response_1, mock_response_2]

        provider = GeminiEmbeddingProvider(api_key="mock-key")
        texts = ["hello"] * 150
        
        embeddings = provider.embed(texts)
        
        assert len(embeddings) == 150
        assert len(embeddings[0]) == 768
        
        # Verify it was called twice (due to batching at 100)
        assert mock_client.models.embed_content.call_count == 2
        
        # Verify the call config
        call_args = mock_client.models.embed_content.call_args_list[0]
        config = call_args.kwargs["config"]
        assert config.task_type == "RETRIEVAL_DOCUMENT"

    @patch("memory_with_receipts.embeddings.gemini.genai.Client")
    def test_embed_single_task_type(self, mock_client_class) -> None:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_emb = MagicMock()
        mock_emb.values = [0.2] * 768
        mock_response = MagicMock()
        mock_response.embeddings = [mock_emb]
        mock_client.models.embed_content.return_value = mock_response

        provider = GeminiEmbeddingProvider(api_key="mock-key")
        emb = provider.embed_single("my query")
        
        assert len(emb) == 768
        assert emb[0] == 0.2
        
        # Verify task type was RETRIEVAL_QUERY
        mock_client.models.embed_content.assert_called_once()
        config = mock_client.models.embed_content.call_args.kwargs["config"]
        assert config.task_type == "RETRIEVAL_QUERY"

    @patch("memory_with_receipts.embeddings.gemini.genai.Client")
    def test_api_failure_raises_embedding_error(self, mock_client_class) -> None:
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = Exception("API Key Expired")
        mock_client_class.return_value = mock_client

        provider = GeminiEmbeddingProvider(api_key="mock-key")
        
        with pytest.raises(EmbeddingError, match="Gemini embedding generation failed"):
            provider.embed(["text"])
