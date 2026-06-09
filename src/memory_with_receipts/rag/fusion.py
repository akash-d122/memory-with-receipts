"""Reciprocal Rank Fusion for merging vector and keyword search results.

Pure function — no database access. Merges two ranked result lists into a
single fused ranking using the RRF formula: score = Σ 1/(k + rank_i).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class RRFResult:
    """A single fused search result with score breakdown."""

    chunk_id: UUID
    rrf_score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None
    vector_score: float | None = None
    keyword_score: float | None = None
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RankedItem:
    """A search result from a single retrieval source."""

    chunk_id: UUID
    score: float


def reciprocal_rank_fusion(
    vector_results: list[RankedItem],
    keyword_results: list[RankedItem],
    k: int = 60,
) -> list[RRFResult]:
    """Merge vector and keyword search results using Reciprocal Rank Fusion.

    Args:
        vector_results: Ranked results from vector search (best first).
        keyword_results: Ranked results from keyword search (best first).
        k: RRF smoothing constant (default 60, standard in literature).

    Returns:
        Fused results sorted by RRF score descending.
    """
    # Build per-chunk tracking
    chunks: dict[UUID, dict] = {}

    for rank, item in enumerate(vector_results, start=1):
        entry = chunks.setdefault(str(item.chunk_id), {
            "chunk_id": item.chunk_id,
            "rrf_score": 0.0,
            "vector_rank": None,
            "keyword_rank": None,
            "vector_score": None,
            "keyword_score": None,
        })
        entry["vector_rank"] = rank
        entry["vector_score"] = item.score
        entry["rrf_score"] += 1.0 / (k + rank)

    for rank, item in enumerate(keyword_results, start=1):
        entry = chunks.setdefault(str(item.chunk_id), {
            "chunk_id": item.chunk_id,
            "rrf_score": 0.0,
            "vector_rank": None,
            "keyword_rank": None,
            "vector_score": None,
            "keyword_score": None,
        })
        entry["keyword_rank"] = rank
        entry["keyword_score"] = item.score
        entry["rrf_score"] += 1.0 / (k + rank)

    # Build reason codes and final results
    results: list[RRFResult] = []
    for entry in chunks.values():
        reasons: list[str] = []
        has_vector = entry["vector_rank"] is not None
        has_keyword = entry["keyword_rank"] is not None

        if has_vector and has_keyword:
            reasons.append("vector_and_keyword_match")
        elif has_vector:
            reasons.append("vector_match")
        elif has_keyword:
            reasons.append("keyword_match")

        results.append(RRFResult(
            chunk_id=entry["chunk_id"],
            rrf_score=round(entry["rrf_score"], 8),
            vector_rank=entry["vector_rank"],
            keyword_rank=entry["keyword_rank"],
            vector_score=entry["vector_score"],
            keyword_score=entry["keyword_score"],
            reason_codes=reasons,
        ))

    # Sort by RRF score descending, then by chunk_id for determinism
    results.sort(key=lambda r: (-r.rrf_score, str(r.chunk_id)))
    return results
