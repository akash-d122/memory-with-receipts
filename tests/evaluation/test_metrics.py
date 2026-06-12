"""Unit tests for evaluation metric functions.

All metrics are pure functions — no DB, no LLM, no Docker required.
"""

from __future__ import annotations

from memory_with_receipts.evaluation.metrics import (
    citation_count_check,
    context_precision,
    context_recall_at_k,
    must_include_terms_check,
    must_not_include_terms_check,
    receipt_coverage,
    source_hit_rate,
    valid_citation_coverage,
)
from memory_with_receipts.llm.citations import CitationReceipt
from memory_with_receipts.llm.generation import AskResult
from memory_with_receipts.rag.search_service import SearchResultData

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_citation(
    index: int = 1,
    doc_title: str = "Doc A",
    chunk_id: str = "chunk-001",
    document_id: str = "doc-001",
    rrf_score: float = 0.5,
) -> CitationReceipt:
    return CitationReceipt(
        citation_index=index,
        chunk_id=chunk_id,
        document_id=document_id,
        document_title=doc_title,
        source_type="text",
        uri=None,
        chunk_index=0,
        section_title=None,
        heading_path=None,
        start_char=0,
        end_char=100,
        content_snippet="Some content snippet here.",
        vector_score=None,
        keyword_score=0.8,
        rrf_score=rrf_score,
    )


def _make_chunk(doc_title: str = "Doc A", rrf_score: float = 0.5) -> SearchResultData:
    return SearchResultData(
        chunk_id="chunk-001",
        document_id="doc-001",
        document_title=doc_title,
        source_type="text",
        uri=None,
        chunk_index=0,
        content="Some content here.",
        section_title=None,
        heading_path=None,
        start_char=0,
        end_char=100,
        vector_score=None,
        keyword_score=0.8,
        rrf_score=rrf_score,
        reason_codes=["keyword"],
        embedding_provider=None,
        embedding_model=None,
    )


def _make_ask_result(
    answer: str = "The answer is here [1].",
    citations: list[CitationReceipt] | None = None,
    context_chunks_used: int = 1,
    is_insufficient: bool = False,
) -> AskResult:
    return AskResult(
        query="test query",
        answer=answer,
        citations=citations or [],
        is_insufficient=is_insufficient,
        context_chunks_used=context_chunks_used,
        model="mock",
        provider="mock",
    )


# ── source_hit_rate ───────────────────────────────────────────────────────────

class TestSourceHitRate:
    def test_full_match_score_1(self) -> None:
        citations = [_make_citation(doc_title="Doc A"), _make_citation(doc_title="Doc B", index=2)]
        result = source_hit_rate(citations, expected_titles=["Doc A", "Doc B"])
        assert result.passed is True
        assert result.score == 1.0
        assert result.name == "source_hit_rate"

    def test_partial_match_score_half(self) -> None:
        citations = [_make_citation(doc_title="Doc A")]
        result = source_hit_rate(citations, expected_titles=["Doc A", "Doc B"])
        assert result.passed is False
        assert result.score == 0.5

    def test_no_match_score_zero(self) -> None:
        citations = [_make_citation(doc_title="Doc X")]
        result = source_hit_rate(citations, expected_titles=["Doc A"])
        assert result.passed is False
        assert result.score == 0.0

    def test_empty_expected_trivially_passes(self) -> None:
        result = source_hit_rate([], expected_titles=[])
        assert result.passed is True
        assert result.score == 1.0

    def test_case_insensitive_match(self) -> None:
        citations = [_make_citation(doc_title="internal wiki: database access")]
        result = source_hit_rate(
            citations, expected_titles=["Internal Wiki: Database Access"]
        )
        assert result.passed is True

    def test_empty_citations_with_expectations_fails(self) -> None:
        result = source_hit_rate([], expected_titles=["Doc A"])
        assert result.passed is False
        assert result.score == 0.0


# ── context_recall_at_k ───────────────────────────────────────────────────────

class TestContextRecallAtK:
    def test_full_recall(self) -> None:
        chunks = [_make_chunk("Doc A"), _make_chunk("Doc B")]
        result = context_recall_at_k(chunks, expected_titles=["Doc A", "Doc B"], k=5)
        assert result.passed is True
        assert result.score == 1.0

    def test_partial_recall(self) -> None:
        chunks = [_make_chunk("Doc A"), _make_chunk("Doc X")]
        result = context_recall_at_k(chunks, expected_titles=["Doc A", "Doc B"], k=5)
        assert result.score == 0.5
        assert result.passed is False

    def test_k_limits_window(self) -> None:
        # Doc B is at index 2 (0-based), k=1 so only first chunk checked
        chunks = [_make_chunk("Doc A"), _make_chunk("Doc B")]
        result = context_recall_at_k(chunks, expected_titles=["Doc B"], k=1)
        assert result.score == 0.0
        assert result.passed is False

    def test_empty_expected_trivially_passes(self) -> None:
        chunks = [_make_chunk("Doc A")]
        result = context_recall_at_k(chunks, expected_titles=[], k=5)
        assert result.passed is True


# ── context_precision ─────────────────────────────────────────────────────────

class TestContextPrecision:
    def test_all_relevant(self) -> None:
        chunks = [_make_chunk("Doc A"), _make_chunk("Doc A")]
        result = context_precision(chunks, expected_titles=["Doc A"], k=5)
        assert result.score == 1.0
        assert result.passed is True

    def test_half_relevant(self) -> None:
        chunks = [_make_chunk("Doc A"), _make_chunk("Doc X")]
        result = context_precision(chunks, expected_titles=["Doc A"], k=5)
        assert result.score == 0.5
        assert result.passed is True  # 0.5 >= 0.5 threshold

    def test_none_relevant(self) -> None:
        chunks = [_make_chunk("Doc X"), _make_chunk("Doc Y")]
        result = context_precision(chunks, expected_titles=["Doc A"], k=5)
        assert result.score == 0.0
        assert result.passed is False

    def test_no_chunks_fails(self) -> None:
        result = context_precision([], expected_titles=["Doc A"], k=5)
        assert result.passed is False
        assert result.score == 0.0

    def test_empty_expected_trivially_passes(self) -> None:
        chunks = [_make_chunk("Doc X")]
        result = context_precision(chunks, expected_titles=[], k=5)
        assert result.passed is True


# ── valid_citation_coverage ───────────────────────────────────────────────────

class TestValidCitationCoverage:
    def test_all_valid_citations(self) -> None:
        citations = [_make_citation(index=1)]
        result_obj = _make_ask_result(citations=citations, context_chunks_used=1)
        result = valid_citation_coverage(result_obj)
        assert result.passed is True
        assert result.score == 1.0

    def test_out_of_range_citation_fails(self) -> None:
        # Citation index 5 but only 1 chunk available
        citations = [_make_citation(index=5)]
        result_obj = _make_ask_result(citations=citations, context_chunks_used=1)
        result = valid_citation_coverage(result_obj)
        assert result.passed is False

    def test_insufficient_context_trivially_passes(self) -> None:
        result_obj = _make_ask_result(is_insufficient=True, context_chunks_used=0)
        result = valid_citation_coverage(result_obj)
        assert result.passed is True

    def test_no_citations_with_context_fails(self) -> None:
        result_obj = _make_ask_result(citations=[], context_chunks_used=3)
        result = valid_citation_coverage(result_obj)
        assert result.passed is False
        assert result.score == 0.0


# ── receipt_coverage ──────────────────────────────────────────────────────────

class TestReceiptCoverage:
    def test_complete_receipts_pass(self) -> None:
        citations = [_make_citation()]
        result = receipt_coverage(citations)
        assert result.passed is True
        assert result.score == 1.0

    def test_missing_chunk_id_fails(self) -> None:
        c = _make_citation(chunk_id="")
        result = receipt_coverage([c])
        assert result.passed is False

    def test_missing_document_id_fails(self) -> None:
        c = _make_citation(document_id="")
        result = receipt_coverage([c])
        assert result.passed is False

    def test_negative_rrf_score_fails(self) -> None:
        c = _make_citation(rrf_score=-1.0)
        result = receipt_coverage([c])
        assert result.passed is False

    def test_empty_citations_trivially_passes(self) -> None:
        result = receipt_coverage([])
        assert result.passed is True


# ── citation_count_check ──────────────────────────────────────────────────────

class TestCitationCountCheck:
    def test_meets_minimum(self) -> None:
        citations = [_make_citation(index=1), _make_citation(index=2)]
        result = citation_count_check(citations, min_citation_count=2)
        assert result.passed is True
        assert result.score == 1.0

    def test_exceeds_minimum(self) -> None:
        citations = [_make_citation(index=1), _make_citation(index=2)]
        result = citation_count_check(citations, min_citation_count=1)
        assert result.passed is True

    def test_below_minimum(self) -> None:
        citations = [_make_citation(index=1)]
        result = citation_count_check(citations, min_citation_count=2)
        assert result.passed is False
        assert result.score == 0.5

    def test_zero_minimum_always_passes(self) -> None:
        result = citation_count_check([], min_citation_count=0)
        assert result.passed is True


# ── must_include_terms ────────────────────────────────────────────────────────

class TestMustIncludeTerms:
    def test_all_terms_present(self) -> None:
        result = must_include_terms_check("Use Teleport proxy service", ["Teleport", "proxy"])
        assert result.passed is True
        assert result.score == 1.0

    def test_missing_term_fails(self) -> None:
        result = must_include_terms_check("Use Teleport service", ["Teleport", "proxy"])
        assert result.passed is False
        assert result.score == 0.5

    def test_case_insensitive(self) -> None:
        result = must_include_terms_check("use teleport proxy", ["Teleport", "Proxy"])
        assert result.passed is True

    def test_no_terms_trivially_passes(self) -> None:
        result = must_include_terms_check("anything", [])
        assert result.passed is True

    def test_all_terms_missing_score_zero(self) -> None:
        result = must_include_terms_check("unrelated answer", ["Teleport", "proxy"])
        assert result.passed is False
        assert result.score == 0.0


# ── must_not_include_terms ────────────────────────────────────────────────────

class TestMustNotIncludeTerms:
    def test_no_violations_passes(self) -> None:
        result = must_not_include_terms_check("Access via Teleport proxy", ["plaintext"])
        assert result.passed is True
        assert result.score == 1.0

    def test_violation_fails(self) -> None:
        result = must_not_include_terms_check(
            "Your plaintext password is here", ["plaintext"]
        )
        assert result.passed is False
        assert result.score == 0.0

    def test_case_insensitive_violation(self) -> None:
        result = must_not_include_terms_check(
            "Here is your Plaintext key", ["plaintext"]
        )
        assert result.passed is False

    def test_no_terms_trivially_passes(self) -> None:
        result = must_not_include_terms_check("anything", [])
        assert result.passed is True
