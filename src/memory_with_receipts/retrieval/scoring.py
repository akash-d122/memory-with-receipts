from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class MemoryCandidate:
    """Candidate memory before final ranking.

    This intentionally stays independent from SQLAlchemy so ranking logic is easy to test.
    """

    memory_id: str
    relevance: float
    confidence: float
    captured_at: datetime
    contradiction_status: str


@dataclass(frozen=True)
class CandidateScore:
    memory_id: str
    total: float
    breakdown: dict[str, float]


def score_candidate(candidate: MemoryCandidate, now: datetime | None = None) -> CandidateScore:
    """Score a memory candidate using simple explainable signals.

    This is not the final retrieval algorithm. It is the first deterministic scoring seam:
    relevance + confidence + recency - contradiction penalty.
    """
    current_time = now or datetime.now(UTC)
    relevance = _clamp(candidate.relevance)
    confidence = _clamp(candidate.confidence)
    recency = _recency_score(candidate.captured_at, current_time)
    contradiction_penalty = -0.5 if candidate.contradiction_status == "contradicted" else 0.0

    breakdown = {
        "relevance": relevance * 0.55,
        "confidence": confidence * 0.25,
        "recency": recency * 0.20,
        "contradiction_penalty": contradiction_penalty,
    }
    total = round(sum(breakdown.values()), 6)
    return CandidateScore(memory_id=candidate.memory_id, total=total, breakdown=breakdown)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _recency_score(captured_at: datetime, now: datetime) -> float:
    age_days = max(0, (now - captured_at).days)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.8
    if age_days <= 180:
        return 0.5
    if age_days <= 365:
        return 0.25
    return 0.1
