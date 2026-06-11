"""Unit tests for MockLLMProvider.

Tests cover: model/provider properties, generate() output shape,
citation marker generation, prompt capture, and token count passthrough.
"""

from __future__ import annotations

from memory_with_receipts.llm.base import GenerationResult
from memory_with_receipts.llm.mock import MockLLMProvider


class TestMockLLMProviderProperties:
    """Tests for BaseLLMProvider interface compliance."""

    def test_model_name_returns_string(self) -> None:
        provider = MockLLMProvider()
        assert isinstance(provider.model_name, str)
        assert len(provider.model_name) > 0

    def test_provider_name_is_mock(self) -> None:
        provider = MockLLMProvider()
        assert provider.provider_name == "mock"

    def test_model_name_is_deterministic(self) -> None:
        p1 = MockLLMProvider()
        p2 = MockLLMProvider()
        assert p1.model_name == p2.model_name


class TestMockLLMProviderGenerate:
    """Tests for generate() return value."""

    def test_returns_generation_result_type(self) -> None:
        provider = MockLLMProvider()
        result = provider.generate("Hello world")
        assert isinstance(result, GenerationResult)

    def test_result_has_non_empty_answer(self) -> None:
        provider = MockLLMProvider()
        result = provider.generate("Test prompt")
        assert len(result.answer) > 0

    def test_raw_prompt_equals_input(self) -> None:
        provider = MockLLMProvider()
        prompt = "What is the capital of France?"
        result = provider.generate(prompt)
        assert result.raw_prompt == prompt

    def test_model_and_provider_in_result(self) -> None:
        provider = MockLLMProvider()
        result = provider.generate("prompt")
        assert result.model == provider.model_name
        assert result.provider == provider.provider_name

    def test_last_prompt_captured(self) -> None:
        provider = MockLLMProvider()
        assert provider.last_prompt == ""
        provider.generate("first call")
        assert provider.last_prompt == "first call"
        provider.generate("second call")
        assert provider.last_prompt == "second call"

    def test_token_counts_none_by_default(self) -> None:
        provider = MockLLMProvider()
        result = provider.generate("test")
        assert result.input_tokens is None
        assert result.output_tokens is None

    def test_token_counts_surfaced_when_configured(self) -> None:
        provider = MockLLMProvider(token_counts=(100, 50))
        result = provider.generate("test")
        assert result.input_tokens == 100
        assert result.output_tokens == 50

    def test_custom_answer_template(self) -> None:
        provider = MockLLMProvider(answer_template="Custom answer {citation_refs} end.")
        result = provider.generate("test")
        assert "Custom answer" in result.answer
        assert "end." in result.answer

    def test_answer_contains_citation_refs_for_context_in_prompt(self) -> None:
        """When prompt has [1], [2] context markers, answer should cite them."""
        provider = MockLLMProvider()
        # Simulate a RAG prompt with 2 numbered context entries
        prompt = "[1] First chunk content\n[2] Second chunk content\n\nQuestion: test\nAnswer:"
        result = provider.generate(prompt)
        # The mock auto-generates citation refs for indices found
        assert "[1]" in result.answer or "[2]" in result.answer

    def test_generate_is_deterministic(self) -> None:
        """Same prompt should always produce same answer."""
        provider = MockLLMProvider()
        r1 = provider.generate("same prompt")
        r2 = provider.generate("same prompt")
        assert r1.answer == r2.answer
