"""Unit tests for citation extraction and CitationReceipt building.

All tests are pure — no DB, no LLM, no Docker required.
"""

from __future__ import annotations

import uuid

from memory_with_receipts.llm.citations import (
    build_citation_receipts,
    extract_citation_indices,
)
from memory_with_receipts.rag.search_service import SearchResultData


def _make_chunk(
    content: str = "Test content",
    title: str = "Doc",
    chunk_index: int = 0,
    rrf_score: float = 0.5,
    vector_score: float | None = 0.8,
    keyword_score: float | None = None,
) -> SearchResultData:
    return SearchResultData(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title=title,
        source_type="text",
        uri="file:///test.txt",
        chunk_index=chunk_index,
        content=content,
        section_title="Section A",
        heading_path="# Section A",
        start_char=0,
        end_char=len(content),
        vector_score=vector_score,
        keyword_score=keyword_score,
        rrf_score=rrf_score,
    )


class TestExtractCitationIndices:
    """Tests for the regex-based citation index extractor."""

    def test_no_citations_returns_empty(self) -> None:
        assert extract_citation_indices("No citations here.") == []

    def test_single_citation(self) -> None:
        assert extract_citation_indices("Answer is here [1].") == [1]

    def test_multiple_citations(self) -> None:
        result = extract_citation_indices("See [1] and [3] and also [2].")
        assert result == [1, 2, 3]

    def test_duplicate_citations_deduplicated(self) -> None:
        result = extract_citation_indices("[1] is cited twice [1] and also [2].")
        assert result == [1, 2]

    def test_returns_sorted_order(self) -> None:
        result = extract_citation_indices("[3] then [1] then [2].")
        assert result == [1, 2, 3]

    def test_large_citation_numbers(self) -> None:
        result = extract_citation_indices("See [10] and [20].")
        assert result == [10, 20]

    def test_zero_citation_excluded(self) -> None:
        """[0] is not a valid citation index (1-based)."""
        result = extract_citation_indices("Bad [0] marker.")
        assert 0 not in result

    def test_answer_with_no_brackets(self) -> None:
        assert extract_citation_indices("Plain text answer.") == []


class TestBuildCitationReceipts:
    """Tests for build_citation_receipts() mapping and filtering."""

    def test_valid_citation_maps_to_receipt(self) -> None:
        chunk = _make_chunk(content="PostgreSQL setup", title="Ops Guide")
        receipts = build_citation_receipts("Answer [1].", [chunk])
        assert len(receipts) == 1
        r = receipts[0]
        assert r.citation_index == 1
        assert r.document_title == "Ops Guide"
        assert r.content_snippet == "PostgreSQL setup"

    def test_multiple_citations_map_correctly(self) -> None:
        chunks = [_make_chunk(title=f"Doc {i}") for i in range(3)]
        receipts = build_citation_receipts("See [1] and [3].", chunks)
        assert len(receipts) == 2
        indices = [r.citation_index for r in receipts]
        assert 1 in indices
        assert 3 in indices

    def test_out_of_range_citation_dropped(self) -> None:
        """[5] when only 2 chunks exist should be silently ignored."""
        chunks = [_make_chunk(), _make_chunk()]
        receipts = build_citation_receipts("See [5].", chunks)
        assert len(receipts) == 0

    def test_receipt_has_all_provenance_fields(self) -> None:
        chunk = _make_chunk(
            content="Long enough content for a snippet test.",
            vector_score=0.9,
            keyword_score=0.7,
            rrf_score=0.8,
        )
        receipts = build_citation_receipts("[1]", [chunk])
        r = receipts[0]
        assert r.chunk_id == chunk.chunk_id
        assert r.document_id == chunk.document_id
        assert r.source_type == chunk.source_type
        assert r.uri == chunk.uri
        assert r.chunk_index == chunk.chunk_index
        assert r.section_title == chunk.section_title
        assert r.heading_path == chunk.heading_path
        assert r.start_char == chunk.start_char
        assert r.end_char == chunk.end_char
        assert r.vector_score == 0.9
        assert r.keyword_score == 0.7
        assert r.rrf_score == 0.8

    def test_content_snippet_truncated_to_200_chars(self) -> None:
        long_content = "x" * 500
        chunk = _make_chunk(content=long_content)
        receipts = build_citation_receipts("[1]", [chunk])
        assert len(receipts[0].content_snippet) == 200

    def test_short_content_not_padded(self) -> None:
        chunk = _make_chunk(content="short")
        receipts = build_citation_receipts("[1]", [chunk])
        assert receipts[0].content_snippet == "short"

    def test_empty_answer_returns_empty(self) -> None:
        chunks = [_make_chunk()]
        receipts = build_citation_receipts("", chunks)
        assert receipts == []

    def test_no_chunks_returns_empty(self) -> None:
        receipts = build_citation_receipts("[1][2]", [])
        assert receipts == []

    def test_receipts_sorted_by_citation_index(self) -> None:
        chunks = [_make_chunk(title=f"Doc {i}") for i in range(3)]
        receipts = build_citation_receipts("[3] then [1] then [2].", chunks)
        indices = [r.citation_index for r in receipts]
        assert indices == sorted(indices)
