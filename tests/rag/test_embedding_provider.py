"""Unit tests for embedding providers.

These tests run without Docker, without model downloads, and without
sentence-transformers installed. They validate the provider interfaces
and mock behavior only.
"""

import math
from unittest.mock import patch

import pytest

from memory_with_receipts.core.exceptions import EmbeddingError
from memory_with_receipts.embeddings.base import BaseEmbeddingProvider
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider


class TestMockEmbeddingProvider:
    """Tests for MockEmbeddingProvider deterministic behavior."""

    @pytest.fixture
    def provider(self) -> MockEmbeddingProvider:
        return MockEmbeddingProvider(dimension=384)

    def test_mock_embed_returns_correct_dimension(
        self, provider: MockEmbeddingProvider
    ) -> None:
        """Vectors must have the configured dimension."""
        vectors = provider.embed(["hello world"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 384

    def test_mock_embed_custom_dimension(self) -> None:
        """Custom dimension must be respected."""
        provider = MockEmbeddingProvider(dimension=128)
        vectors = provider.embed(["test"])
        assert len(vectors[0]) == 128

    def test_mock_embed_deterministic(self, provider: MockEmbeddingProvider) -> None:
        """Same input text must always produce the same vector."""
        text = "deterministic test input"
        v1 = provider.embed([text])
        v2 = provider.embed([text])
        assert v1 == v2

    def test_mock_embed_batch(self, provider: MockEmbeddingProvider) -> None:
        """Batch of N texts must return N vectors."""
        texts = ["first", "second", "third"]
        vectors = provider.embed(texts)
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 384

    def test_mock_embed_different_inputs_different_vectors(
        self, provider: MockEmbeddingProvider
    ) -> None:
        """Different inputs must produce different vectors."""
        vectors = provider.embed(["alpha", "beta"])
        assert vectors[0] != vectors[1]

    def test_mock_embed_normalized(self, provider: MockEmbeddingProvider) -> None:
        """All vectors must have unit length (L2 norm ≈ 1.0)."""
        texts = ["normalize test A", "normalize test B", "normalize test C"]
        vectors = provider.embed(texts)
        for vec in vectors:
            magnitude = math.sqrt(sum(x * x for x in vec))
            assert abs(magnitude - 1.0) < 1e-6, f"Expected unit vector, got magnitude {magnitude}"

    def test_mock_provider_metadata(self, provider: MockEmbeddingProvider) -> None:
        """Provider properties must report correct metadata."""
        assert provider.model_name == "mock-embedding-model"
        assert provider.dimension == 384
        assert provider.provider_name == "mock"

    def test_mock_provider_custom_model_name(self) -> None:
        """Custom model name override must be reflected."""
        provider = MockEmbeddingProvider(model_name_override="custom-mock")
        assert provider.model_name == "custom-mock"

    def test_mock_empty_batch(self, provider: MockEmbeddingProvider) -> None:
        """Empty input list must return empty output list."""
        vectors = provider.embed([])
        assert vectors == []


class TestBaseEmbeddingProvider:
    """Tests for BaseEmbeddingProvider ABC methods."""

    @pytest.fixture
    def provider(self) -> MockEmbeddingProvider:
        return MockEmbeddingProvider(dimension=384)

    def test_dimension_mismatch_raises(self, provider: MockEmbeddingProvider) -> None:
        """validate_dimension must raise EmbeddingError for wrong-length vector."""
        wrong_vector = [0.1] * 128  # 128 != 384
        with pytest.raises(EmbeddingError, match="dimension mismatch"):
            provider.validate_dimension(wrong_vector)

    def test_dimension_match_passes(self, provider: MockEmbeddingProvider) -> None:
        """validate_dimension must pass silently for correct-length vector."""
        correct_vector = [0.1] * 384
        provider.validate_dimension(correct_vector)  # Should not raise

    def test_embed_single_delegates(self, provider: MockEmbeddingProvider) -> None:
        """embed_single must call embed with single-element list and return first result."""
        text = "single embed test"
        single_result = provider.embed_single(text)
        batch_result = provider.embed([text])
        assert single_result == batch_result[0]

    def test_base_is_abstract(self) -> None:
        """BaseEmbeddingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseEmbeddingProvider()  # type: ignore[abstract]


class TestLocalEmbeddingProvider:
    """Tests for LocalEmbeddingProvider without loading any model."""

    def test_local_provider_import_error(self) -> None:
        """Must raise EmbeddingError if sentence-transformers is not installed."""
        from memory_with_receipts.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()

        # Mock the import to simulate sentence-transformers not being installed
        with (
            patch.dict("sys.modules", {"sentence_transformers": None}),
            pytest.raises(EmbeddingError, match="sentence-transformers is not installed"),
        ):
            provider.embed(["test"])

    def test_local_provider_lazy_loading(self) -> None:
        """Model must NOT be loaded at construction time."""
        from memory_with_receipts.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        # At construction, _model should be None (no model loaded)
        assert provider._model is None

    def test_local_provider_metadata(self) -> None:
        """Provider properties must report correct metadata without loading model."""
        from memory_with_receipts.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.model_name == "all-MiniLM-L6-v2"
        assert provider.dimension == 384
        assert provider.provider_name == "local"

    def test_local_provider_custom_model(self) -> None:
        """Custom model name and dimension must be stored without loading model."""
        from memory_with_receipts.embeddings.local import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(
            model_name="custom-model",
            dimension=768,
        )
        assert provider.model_name == "custom-model"
        assert provider.dimension == 768
        # Still no model loaded
        assert provider._model is None
