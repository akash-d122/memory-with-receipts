from datetime import UTC, datetime, timedelta

from memory_with_receipts.retrieval.scoring import MemoryCandidate, score_candidate


def test_score_candidate_penalizes_contradicted_memory():
    now = datetime.now(UTC)
    active = MemoryCandidate(
        memory_id="active-1",
        relevance=0.8,
        confidence=0.8,
        captured_at=now,
        contradiction_status="active",
    )
    contradicted = MemoryCandidate(
        memory_id="contradicted-1",
        relevance=0.8,
        confidence=0.8,
        captured_at=now,
        contradiction_status="contradicted",
    )

    active_score = score_candidate(active, now=now)
    contradicted_score = score_candidate(contradicted, now=now)

    assert active_score.total > contradicted_score.total
    assert contradicted_score.breakdown["contradiction_penalty"] < 0


def test_score_candidate_rewards_more_recent_memory_when_other_signals_match():
    now = datetime.now(UTC)
    recent = MemoryCandidate(
        memory_id="recent-1",
        relevance=0.7,
        confidence=0.7,
        captured_at=now - timedelta(days=1),
        contradiction_status="active",
    )
    old = MemoryCandidate(
        memory_id="old-1",
        relevance=0.7,
        confidence=0.7,
        captured_at=now - timedelta(days=365),
        contradiction_status="active",
    )

    recent_score = score_candidate(recent, now=now)
    old_score = score_candidate(old, now=now)

    assert recent_score.total > old_score.total
    assert recent_score.breakdown["recency"] > old_score.breakdown["recency"]
