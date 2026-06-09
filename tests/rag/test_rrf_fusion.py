"""Deterministic unit tests for Reciprocal Rank Fusion."""

import uuid

from memory_with_receipts.rag.fusion import RankedItem, reciprocal_rank_fusion


def _make_item(score: float) -> RankedItem:
    return RankedItem(chunk_id=uuid.uuid4(), score=score)


def _make_items(n: int) -> list[RankedItem]:
    return [_make_item(score=1.0 - i * 0.1) for i in range(n)]


class TestRRFBasicMerge:
    """Tests for basic RRF merging behavior."""

    def test_merge_two_ranked_lists(self) -> None:
        """RRF must merge two ranked lists into a single fused ranking."""
        vector = _make_items(3)
        keyword = _make_items(3)
        results = reciprocal_rank_fusion(vector, keyword)

        # All 6 unique chunks should appear
        assert len(results) == 6

    def test_overlapping_chunks_get_higher_scores(self) -> None:
        """Chunks appearing in both lists must score higher than single-source."""
        shared_id = uuid.uuid4()
        vector = [RankedItem(chunk_id=shared_id, score=0.9)]
        keyword = [RankedItem(chunk_id=shared_id, score=0.8)]
        vector_only = [RankedItem(chunk_id=uuid.uuid4(), score=0.95)]

        results = reciprocal_rank_fusion(
            vector + vector_only, keyword, k=60
        )

        # Shared chunk should be first (appears in both lists)
        assert results[0].chunk_id == shared_id
        assert results[0].rrf_score > results[1].rrf_score

    def test_scores_are_deterministic(self) -> None:
        """Same inputs must produce identical scores."""
        cid1, cid2 = uuid.uuid4(), uuid.uuid4()
        vector = [RankedItem(chunk_id=cid1, score=0.9), RankedItem(chunk_id=cid2, score=0.7)]
        keyword = [RankedItem(chunk_id=cid2, score=0.8), RankedItem(chunk_id=cid1, score=0.6)]

        r1 = reciprocal_rank_fusion(vector, keyword)
        r2 = reciprocal_rank_fusion(vector, keyword)

        assert [r.rrf_score for r in r1] == [r.rrf_score for r in r2]
        assert [r.chunk_id for r in r1] == [r.chunk_id for r in r2]

    def test_rrf_formula_correct(self) -> None:
        """Verify the RRF formula: score = 1/(k+rank) per list."""
        k = 60
        cid = uuid.uuid4()
        vector = [RankedItem(chunk_id=cid, score=0.9)]
        keyword = [RankedItem(chunk_id=cid, score=0.8)]

        results = reciprocal_rank_fusion(vector, keyword, k=k)
        expected = round(1.0 / (k + 1) + 1.0 / (k + 1), 8)

        assert len(results) == 1
        assert results[0].rrf_score == expected


class TestRRFSingleSource:
    """Tests for single-source (vector-only or keyword-only) results."""

    def test_vector_only_results(self) -> None:
        """Vector-only results produce valid RRF scores."""
        vector = _make_items(3)
        results = reciprocal_rank_fusion(vector, [])

        assert len(results) == 3
        # All should have vector_rank but no keyword_rank
        for r in results:
            assert r.vector_rank is not None
            assert r.keyword_rank is None

    def test_keyword_only_results(self) -> None:
        """Keyword-only results produce valid RRF scores."""
        keyword = _make_items(3)
        results = reciprocal_rank_fusion([], keyword)

        assert len(results) == 3
        for r in results:
            assert r.vector_rank is None
            assert r.keyword_rank is not None


class TestRRFEmptyInputs:
    """Tests for empty input handling."""

    def test_both_empty(self) -> None:
        """Empty inputs return empty results."""
        results = reciprocal_rank_fusion([], [])
        assert results == []

    def test_empty_vector(self) -> None:
        """Empty vector list still returns keyword results."""
        keyword = _make_items(2)
        results = reciprocal_rank_fusion([], keyword)
        assert len(results) == 2

    def test_empty_keyword(self) -> None:
        """Empty keyword list still returns vector results."""
        vector = _make_items(2)
        results = reciprocal_rank_fusion(vector, [])
        assert len(results) == 2


class TestRRFReasonCodes:
    """Tests for reason code assignment."""

    def test_vector_and_keyword_match(self) -> None:
        """Chunks in both lists get 'vector_and_keyword_match'."""
        cid = uuid.uuid4()
        vector = [RankedItem(chunk_id=cid, score=0.9)]
        keyword = [RankedItem(chunk_id=cid, score=0.8)]

        results = reciprocal_rank_fusion(vector, keyword)
        assert results[0].reason_codes == ["vector_and_keyword_match"]

    def test_vector_only_reason(self) -> None:
        """Chunks only in vector list get 'vector_match'."""
        vector = _make_items(1)
        results = reciprocal_rank_fusion(vector, [])
        assert results[0].reason_codes == ["vector_match"]

    def test_keyword_only_reason(self) -> None:
        """Chunks only in keyword list get 'keyword_match'."""
        keyword = _make_items(1)
        results = reciprocal_rank_fusion([], keyword)
        assert results[0].reason_codes == ["keyword_match"]


class TestRRFScoreBreakdown:
    """Tests for score metadata preservation."""

    def test_preserves_vector_score(self) -> None:
        """Original vector score must be preserved in results."""
        cid = uuid.uuid4()
        vector = [RankedItem(chunk_id=cid, score=0.85)]
        results = reciprocal_rank_fusion(vector, [])
        assert results[0].vector_score == 0.85
        assert results[0].keyword_score is None

    def test_preserves_keyword_score(self) -> None:
        """Original keyword score must be preserved in results."""
        cid = uuid.uuid4()
        keyword = [RankedItem(chunk_id=cid, score=0.72)]
        results = reciprocal_rank_fusion([], keyword)
        assert results[0].keyword_score == 0.72
        assert results[0].vector_score is None

    def test_preserves_both_scores(self) -> None:
        """Both scores preserved when chunk appears in both lists."""
        cid = uuid.uuid4()
        vector = [RankedItem(chunk_id=cid, score=0.9)]
        keyword = [RankedItem(chunk_id=cid, score=0.75)]
        results = reciprocal_rank_fusion(vector, keyword)
        assert results[0].vector_score == 0.9
        assert results[0].keyword_score == 0.75
