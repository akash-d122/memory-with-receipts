"""Abstract base class for LLM providers.

Every LLM provider must implement:
- model_name: identifier of the model
- provider_name: human-readable label (e.g. "gemini", "mock")
- generate(prompt): send prompt and return GenerationResult

The base class defines GenerationResult so tests can import it
without depending on any concrete provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenerationResult:
    """Result from a single LLM generation call.

    Attributes:
        answer: LLM-generated text, may contain [N] citation markers.
        raw_prompt: The exact prompt sent (for auditability).
        model: Model identifier string.
        provider: Provider label string.
        input_tokens: Prompt token count if available, else None.
        output_tokens: Completion token count if available, else None.
    """

    answer: str
    raw_prompt: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the underlying LLM model."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider label (e.g. 'gemini', 'mock')."""

    @abstractmethod
    def generate(self, prompt: str) -> GenerationResult:
        """Send a prompt and return a GenerationResult.

        Args:
            prompt: Complete prompt string to send to the LLM.

        Returns:
            GenerationResult with the generated answer and metadata.

        Raises:
            GenerationError: If the LLM call fails.
        """
