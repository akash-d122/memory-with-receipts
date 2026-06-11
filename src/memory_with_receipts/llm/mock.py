"""Deterministic mock LLM provider for unit testing.

MockLLMProvider never makes network calls. It returns a canned response
that references every context chunk number so citation extraction tests
always have predictable citation indices to assert against.
"""

from __future__ import annotations

from memory_with_receipts.llm.base import BaseLLMProvider, GenerationResult

_DEFAULT_ANSWER_TEMPLATE = (
    "Based on the provided context, here is the answer to your question. "
    "{citation_refs} The information comes from multiple sources."
)


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for deterministic unit tests.

    Args:
        answer_template: Template string used to build the response.
            Use ``{citation_refs}`` as a placeholder for auto-generated
            ``[1] [2] ...`` references.  If omitted, a sensible default
            is used.
        token_counts: Optional (input, output) token count tuple to
            surface in GenerationResult for testing.
    """

    def __init__(
        self,
        answer_template: str | None = None,
        token_counts: tuple[int, int] | None = None,
    ) -> None:
        self._answer_template = answer_template or _DEFAULT_ANSWER_TEMPLATE
        self._token_counts = token_counts
        self._last_prompt: str = ""

    @property
    def model_name(self) -> str:
        return "mock-llm-model"

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def last_prompt(self) -> str:
        """The most-recently sent prompt (useful in test assertions)."""
        return self._last_prompt

    def generate(self, prompt: str) -> GenerationResult:
        """Return a deterministic response citing all context chunks.

        The number of citation references is inferred by counting numbered
        context markers ``[1]``, ``[2]`` … in the prompt itself.
        """
        self._last_prompt = prompt

        # Count how many numbered context entries are in the prompt
        import re
        indices = sorted({int(m) for m in re.findall(r"^\[(\d+)\]", prompt, re.MULTILINE)})
        citation_refs = " ".join(f"[{i}]" for i in indices) if indices else "[1]"

        answer = self._answer_template.format(citation_refs=citation_refs)

        input_tokens, output_tokens = self._token_counts or (None, None)
        return GenerationResult(
            answer=answer,
            raw_prompt=prompt,
            model=self.model_name,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
