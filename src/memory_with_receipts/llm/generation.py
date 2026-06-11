"""Generation pipeline — orchestrates retrieval → prompt → LLM → citations.

Pipeline inside GenerationService.ask():
  1. Retrieve top-k chunks via SearchService
  2. If no chunks → return is_insufficient=True with canned message
  3. Build prompt via build_rag_prompt()
  4. Call llm_provider.generate(prompt)
  5. Detect INSUFFICIENT_CONTEXT sentinel in answer
  6. Extract citations via build_citation_receipts()
  7. Return AskResult with all fields populated
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from memory_with_receipts.core.exceptions import GenerationError, RetrievalError
from memory_with_receipts.llm.base import BaseLLMProvider
from memory_with_receipts.llm.citations import CitationReceipt, build_citation_receipts
from memory_with_receipts.llm.prompts import INSUFFICIENT_CONTEXT_MARKER, build_rag_prompt
from memory_with_receipts.rag.search_service import SearchResultData, SearchService

_INSUFFICIENT_ANSWER = "I do not have enough evidence to answer this question."


@dataclass
class AskResult:
    """Complete result from a single /v1/ask call.

    Attributes:
        query: Original user question.
        answer: LLM-generated answer (citations stripped to inline markers).
        citations: CitationReceipt list — one per unique valid [N] in answer.
        is_insufficient: True when context was empty or LLM returned sentinel.
        context_chunks_used: Number of chunks passed to the LLM.
        model: LLM model identifier.
        provider: LLM provider label.
        raw_prompt: The exact prompt string sent (for audit/debug).
        retrieval_time_ms: Time spent in SearchService.search().
        generation_time_ms: Time spent in llm_provider.generate().
        input_tokens: Prompt token count (None if provider does not report it).
        output_tokens: Completion token count (None if not reported).
    """

    query: str
    answer: str
    citations: list[CitationReceipt] = field(default_factory=list)
    is_insufficient: bool = False
    context_chunks_used: int = 0
    model: str = ""
    provider: str = ""
    raw_prompt: str = ""
    retrieval_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None


class GenerationService:
    """Orchestrates RAG answer generation with inline citations.

    Args:
        llm_provider: Any BaseLLMProvider implementation.
        search_service: Configured SearchService for retrieval.
        default_top_k: Default number of chunks to retrieve if not overridden.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        search_service: SearchService,
        default_top_k: int = 5,
    ) -> None:
        self._llm = llm_provider
        self._search_service = search_service
        self._default_top_k = default_top_k

    def ask(
        self,
        session: Session,
        query: str,
        top_k: int | None = None,
        source_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> AskResult:
        """Execute RAG pipeline and return a grounded answer with citations.

        Args:
            session: SQLAlchemy session for DB queries.
            query: Natural-language question from the user.
            top_k: Number of context chunks to retrieve (overrides default).
            source_type: Optional filter by document source_type.
            date_from: Optional ingested_at lower bound.
            date_to: Optional ingested_at upper bound.
            metadata_filters: Optional key-value document metadata filters.

        Returns:
            AskResult with answer, citations, timing, and token metadata.

        Raises:
            GenerationError: If the LLM call fails.
            RetrievalError: If retrieval fails.
        """
        k = top_k if top_k is not None else self._default_top_k

        # Detect dialect: pgvector <=> only works on Postgres
        dialect = session.bind.dialect.name if session.bind else "sqlite"
        enable_vector = dialect == "postgresql"
        enable_keyword = True

        # ── 1. Retrieve ──────────────────────────────────────────────────────
        t0 = time.monotonic()
        try:
            chunks: list[SearchResultData] = self._search_service.search(
                session=session,
                query=query,
                top_k=k,
                source_type=source_type,
                date_from=date_from,
                date_to=date_to,
                metadata_filters=metadata_filters,
                enable_vector=enable_vector,
                enable_keyword=enable_keyword,
            )
        except Exception as exc:
            if not isinstance(exc, RetrievalError):
                raise RetrievalError(f"Retrieval failed: {exc}") from exc
            raise
        retrieval_ms = round((time.monotonic() - t0) * 1000, 2)

        # ── 2. Short-circuit if no context ───────────────────────────────────
        if not chunks:
            return AskResult(
                query=query,
                answer=_INSUFFICIENT_ANSWER,
                citations=[],
                is_insufficient=True,
                context_chunks_used=0,
                model=self._llm.model_name,
                provider=self._llm.provider_name,
                raw_prompt="",
                retrieval_time_ms=retrieval_ms,
                generation_time_ms=0.0,
            )

        # ── 3. Build prompt ───────────────────────────────────────────────────
        prompt = build_rag_prompt(query, chunks)

        # ── 4. Generate ───────────────────────────────────────────────────────
        t1 = time.monotonic()
        try:
            gen_result = self._llm.generate(prompt)
        except Exception as exc:
            raise GenerationError(f"LLM generation failed: {exc}") from exc
        generation_ms = round((time.monotonic() - t1) * 1000, 2)

        answer = gen_result.answer

        # ── 5. Detect insufficient-context sentinel ───────────────────────────
        is_insufficient = INSUFFICIENT_CONTEXT_MARKER in answer
        if is_insufficient:
            answer = _INSUFFICIENT_ANSWER
            citations: list[CitationReceipt] = []
        else:
            # ── 6. Extract citations ──────────────────────────────────────────
            citations = build_citation_receipts(answer, chunks)

        return AskResult(
            query=query,
            answer=answer,
            citations=citations,
            is_insufficient=is_insufficient,
            context_chunks_used=len(chunks),
            model=gen_result.model,
            provider=gen_result.provider,
            raw_prompt=gen_result.raw_prompt,
            retrieval_time_ms=retrieval_ms,
            generation_time_ms=generation_ms,
            input_tokens=gen_result.input_tokens,
            output_tokens=gen_result.output_tokens,
        )
