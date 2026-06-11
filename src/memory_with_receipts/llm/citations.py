"""Citation extraction and receipt building.

Pipeline
--------
1. extract_citation_indices(answer_text) → sorted list of 1-based ints
   Regex scans the LLM answer for [N] markers.

2. build_citation_receipts(answer, chunks) → list[CitationReceipt]
   Maps each cited [N] to the SearchResultData at position N-1.
   Out-of-range indices are silently dropped (defensive).

CitationReceipt carries the full provenance: chunk id, document id,
scores, offsets, heading path — everything needed for an audit trail.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from memory_with_receipts.rag.search_service import SearchResultData


@dataclass
class CitationReceipt:
    """Provenance receipt for a single cited chunk.

    citation_index matches the [N] marker in the answer text (1-based).
    content_snippet is the first 200 characters of the chunk content.
    """

    citation_index: int
    chunk_id: str
    document_id: str
    document_title: str
    source_type: str
    uri: str | None
    chunk_index: int
    section_title: str | None
    heading_path: str | None
    start_char: int
    end_char: int
    content_snippet: str
    vector_score: float | None
    keyword_score: float | None
    rrf_score: float


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def extract_citation_indices(answer_text: str) -> list[int]:
    """Return sorted, deduplicated 1-based citation indices from answer text.

    Args:
        answer_text: Raw LLM answer string, possibly containing [N] markers.

    Returns:
        Sorted list of unique positive integers found in [N] markers.
        Empty list if no markers are present.
    """
    raw = {int(m) for m in _CITATION_PATTERN.findall(answer_text)}
    return sorted(i for i in raw if i >= 1)


def build_citation_receipts(
    answer: str,
    context_chunks: list[SearchResultData],
) -> list[CitationReceipt]:
    """Build CitationReceipt objects for every [N] cited in the answer.

    Args:
        answer: LLM answer text containing [N] citation markers.
        context_chunks: Ordered list of SearchResultData (rank 1 = index 0).

    Returns:
        List of CitationReceipt, one per unique valid citation, sorted by
        citation_index. Out-of-range indices are silently dropped.
    """
    indices = extract_citation_indices(answer)
    receipts: list[CitationReceipt] = []

    for idx in indices:
        # Convert 1-based citation to 0-based list position
        pos = idx - 1
        if pos < 0 or pos >= len(context_chunks):
            continue  # defensive: skip bad indices

        chunk = context_chunks[pos]
        receipts.append(
            CitationReceipt(
                citation_index=idx,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                source_type=chunk.source_type,
                uri=chunk.uri,
                chunk_index=chunk.chunk_index,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                content_snippet=chunk.content[:200],
                vector_score=chunk.vector_score,
                keyword_score=chunk.keyword_score,
                rrf_score=chunk.rrf_score,
            )
        )

    return receipts
