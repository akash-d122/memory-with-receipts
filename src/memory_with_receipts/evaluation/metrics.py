"""Deterministic evaluation metric functions.

All functions are pure — no database access, no LLM calls.
Each returns a MetricResult with a pass/fail flag, a numeric score,
and a human-readable detail string.

Metrics:
    source_hit_rate          — expected document titles found in citations
    context_recall_at_k      — expected titles present in top-k retrieved chunks
    context_precision        — fraction of top-k chunks that ARE expected sources
    valid_citation_coverage  — all [N] markers map to real chunks
    receipt_coverage         — all citations carry required provenance fields
    must_include_terms_check — required terms present in the answer
    must_not_include_terms_check — forbidden terms absent from the answer
"""

from __future__ import annotations

from memory_with_receipts.evaluation.schemas import MetricResult
from memory_with_receipts.llm.citations import CitationReceipt
from memory_with_receipts.llm.generation import AskResult
from memory_with_receipts.rag.search_service import SearchResultData

# ── Retrieval metrics ──────────────────────────────────────────────────────────

def source_hit_rate(
    citations: list[CitationReceipt],
    expected_titles: list[str],
) -> MetricResult:
    """Fraction of expected document titles found in citation receipts.

    A title is considered found if any citation's document_title matches
    exactly (case-insensitive).

    Args:
        citations: Citation receipts returned by the RAG pipeline.
        expected_titles: Expected document titles from the golden case.

    Returns:
        MetricResult with score in [0.0, 1.0].
        Passes when score == 1.0 or expected_titles is empty.
    """
    if not expected_titles:
        return MetricResult(
            name="source_hit_rate",
            passed=True,
            score=1.0,
            detail="No expected sources defined — trivially passes.",
        )

    cited_titles = {c.document_title.lower() for c in citations}
    hits = [t for t in expected_titles if t.lower() in cited_titles]
    score = len(hits) / len(expected_titles)
    passed = score == 1.0
    missed = [t for t in expected_titles if t.lower() not in cited_titles]
    detail = (
        f"Found {len(hits)}/{len(expected_titles)} expected sources."
        + (f" Missing: {missed}" if missed else "")
    )
    return MetricResult(name="source_hit_rate", passed=passed, score=score, detail=detail)


def context_recall_at_k(
    chunks: list[SearchResultData],
    expected_titles: list[str],
    k: int,
) -> MetricResult:
    """Fraction of expected sources appearing in the top-k retrieved chunks.

    Args:
        chunks: Retrieved chunks from SearchService (rank order).
        expected_titles: Expected document titles from the golden case.
        k: How many top chunks to consider.

    Returns:
        MetricResult with score in [0.0, 1.0].
        Passes when score == 1.0 or expected_titles is empty.
    """
    if not expected_titles:
        return MetricResult(
            name="context_recall_at_k",
            passed=True,
            score=1.0,
            detail="No expected sources defined — trivially passes.",
        )

    top_k_titles = {c.document_title.lower() for c in chunks[:k]}
    hits = [t for t in expected_titles if t.lower() in top_k_titles]
    score = len(hits) / len(expected_titles)
    passed = score == 1.0
    missed = [t for t in expected_titles if t.lower() not in top_k_titles]
    detail = (
        f"Recall@{k}: {len(hits)}/{len(expected_titles)} expected sources in top-{k} chunks."
        + (f" Missing: {missed}" if missed else "")
    )
    return MetricResult(
        name="context_recall_at_k", passed=passed, score=score, detail=detail
    )


def context_precision(
    chunks: list[SearchResultData],
    expected_titles: list[str],
    k: int,
) -> MetricResult:
    """Fraction of top-k retrieved chunks whose source is an expected title.

    Measures how much noise is in the context window.

    Args:
        chunks: Retrieved chunks from SearchService (rank order).
        expected_titles: Expected document titles from the golden case.
        k: How many top chunks to evaluate.

    Returns:
        MetricResult with score in [0.0, 1.0].
        Passes when score >= 0.5 (at least half the context is relevant),
        or when expected_titles is empty.
    """
    if not expected_titles:
        return MetricResult(
            name="context_precision",
            passed=True,
            score=1.0,
            detail="No expected sources defined — trivially passes.",
        )

    expected_lower = {t.lower() for t in expected_titles}
    top_k = chunks[:k]
    if not top_k:
        return MetricResult(
            name="context_precision",
            passed=False,
            score=0.0,
            detail=f"No chunks retrieved (k={k}).",
        )

    relevant = [c for c in top_k if c.document_title.lower() in expected_lower]
    score = len(relevant) / len(top_k)
    passed = score >= 0.5
    detail = (
        f"Precision@{k}: {len(relevant)}/{len(top_k)} chunks are from expected sources."
    )
    return MetricResult(
        name="context_precision", passed=passed, score=score, detail=detail
    )


# ── Citation metrics ───────────────────────────────────────────────────────────

def valid_citation_coverage(
    result: AskResult,
) -> MetricResult:
    """Check all [N] citation markers in the answer map to real chunks.

    Passes when every citation index is within bounds and min_citation_count
    is satisfied. Note: min_citation_count threshold is checked by the runner
    using a separate dedicated metric; this function only validates integrity.

    Args:
        result: The full AskResult from GenerationService.ask().

    Returns:
        MetricResult — passed when all citations are valid (no out-of-range indices).
    """
    if result.is_insufficient:
        return MetricResult(
            name="valid_citation_coverage",
            passed=True,
            score=1.0,
            detail="is_insufficient=True — citation coverage not applicable.",
        )

    total = len(result.citations)
    invalid = [
        c for c in result.citations
        if c.citation_index < 1 or c.citation_index > result.context_chunks_used
    ]
    if result.context_chunks_used == 0:
        score = 1.0
        passed = True
        detail = "No context chunks used — no citations expected."
    elif total == 0:
        score = 0.0
        passed = False
        detail = "No citations found in answer despite context being available."
    else:
        score = 1.0 - (len(invalid) / total) if total else 1.0
        passed = len(invalid) == 0
        detail = (
            f"{total - len(invalid)}/{total} citations are valid."
            + (f" Invalid indices: {[c.citation_index for c in invalid]}" if invalid else "")
        )
    return MetricResult(
        name="valid_citation_coverage", passed=passed, score=score, detail=detail
    )


def receipt_coverage(
    citations: list[CitationReceipt],
) -> MetricResult:
    """Check all citations carry the required provenance fields.

    Required: chunk_id, document_id, rrf_score (>= 0).

    Args:
        citations: Citation receipts from the answer.

    Returns:
        MetricResult — passed when every citation has all required fields.
    """
    if not citations:
        return MetricResult(
            name="receipt_coverage",
            passed=True,
            score=1.0,
            detail="No citations — receipt coverage trivially passes.",
        )

    incomplete = []
    for c in citations:
        missing_fields = []
        if not c.chunk_id:
            missing_fields.append("chunk_id")
        if not c.document_id:
            missing_fields.append("document_id")
        if c.rrf_score < 0:
            missing_fields.append("rrf_score<0")
        if missing_fields:
            incomplete.append((c.citation_index, missing_fields))

    score = 1.0 - (len(incomplete) / len(citations))
    passed = len(incomplete) == 0
    detail = (
        f"{len(citations) - len(incomplete)}/{len(citations)} citations have complete receipts."
        + (f" Incomplete: {incomplete}" if incomplete else "")
    )
    return MetricResult(
        name="receipt_coverage", passed=passed, score=score, detail=detail
    )


def citation_count_check(
    citations: list[CitationReceipt],
    min_citation_count: int,
) -> MetricResult:
    """Check the answer contains at least min_citation_count citations.

    Args:
        citations: Citation receipts from the answer.
        min_citation_count: Minimum required number of citations (from golden case).

    Returns:
        MetricResult — passed when len(citations) >= min_citation_count.
    """
    count = len(citations)
    passed = count >= min_citation_count
    score = min(1.0, count / max(min_citation_count, 1))
    detail = (
        f"Found {count} citation(s); minimum required: {min_citation_count}."
    )
    return MetricResult(
        name="citation_count_check", passed=passed, score=score, detail=detail
    )


# ── Content / safety metrics ───────────────────────────────────────────────────

def must_include_terms_check(
    answer: str,
    terms: list[str],
) -> MetricResult:
    """Check all required terms appear in the answer (case-insensitive).

    Args:
        answer: LLM-generated answer text.
        terms: List of substrings that must appear.

    Returns:
        MetricResult — passed when all terms are found.
    """
    if not terms:
        return MetricResult(
            name="must_include_terms",
            passed=True,
            score=1.0,
            detail="No must_include_terms defined — trivially passes.",
        )

    answer_lower = answer.lower()
    missing = [t for t in terms if t.lower() not in answer_lower]
    score = (len(terms) - len(missing)) / len(terms)
    passed = len(missing) == 0
    detail = (
        f"{len(terms) - len(missing)}/{len(terms)} required terms found."
        + (f" Missing: {missing}" if missing else "")
    )
    return MetricResult(
        name="must_include_terms", passed=passed, score=score, detail=detail
    )


def must_not_include_terms_check(
    answer: str,
    terms: list[str],
) -> MetricResult:
    """Check no forbidden terms appear in the answer (case-insensitive).

    Args:
        answer: LLM-generated answer text.
        terms: List of substrings that must NOT appear.

    Returns:
        MetricResult — passed when none of the terms are found.
    """
    if not terms:
        return MetricResult(
            name="must_not_include_terms",
            passed=True,
            score=1.0,
            detail="No must_not_include_terms defined — trivially passes.",
        )

    answer_lower = answer.lower()
    violations = [t for t in terms if t.lower() in answer_lower]
    score = 1.0 if not violations else 0.0
    passed = len(violations) == 0
    detail = (
        "No forbidden terms found."
        if passed
        else f"Forbidden terms found: {violations}"
    )
    return MetricResult(
        name="must_not_include_terms", passed=passed, score=score, detail=detail
    )
