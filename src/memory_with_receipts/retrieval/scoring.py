from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from memory_with_receipts.memory.ingestion import _log, _normalize_text, _parse_event_time
from memory_with_receipts.memory.operational_models import MemoryRecord, ProvenanceLink


def score_operational_memories(
    session: Session,
    payload: dict[str, Any],
    limit: int = 10,
    correlation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Score operational memories using deterministic, explainable signals."""
    _log(
        "retrieval_started",
        correlation_id=correlation_id,
        service_name=payload.get("service_name"),
        host_name=payload.get("host_name"),
        category=payload.get("category"),
        limit=limit,
    )
    memories = session.scalars(
        select(MemoryRecord)
        .where(MemoryRecord.status == "active")
        .options(
            selectinload(MemoryRecord.provenance_links).selectinload(ProvenanceLink.source_record),
            selectinload(MemoryRecord.provenance_links).selectinload(
                ProvenanceLink.evidence_record
            ),
        )
    ).all()

    query = _operational_query_profile(payload)
    scored_results = [_score_operational_memory(memory, query) for memory in memories]
    results = [result for result in scored_results if _is_meaningful_operational_match(result, query)]
    results.sort(key=lambda result: (-result["score"], result["memory_key"]))
    final_results = results[:limit]

    for result in final_results:
        _log(
            "retrieval_scored",
            correlation_id=correlation_id,
            memory_record_id=result["memory_id"],
            memory_key=result["memory_key"],
            score=result["score"],
            reasons=result["reasons"],
        )

    _log(
        "retrieval_finished",
        correlation_id=correlation_id,
        candidates_evaluated=len(results),
        results_returned=len(final_results),
    )
    return final_results


def _operational_query_profile(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    return {
        "service_name": str(payload.get("service_name")) if payload.get("service_name") else None,
        "host_name": str(payload.get("host_name")) if payload.get("host_name") else None,
        "environment": (
            _normalize_text(payload.get("environment")) if payload.get("environment") else None
        ),
        "severity": _normalize_text(payload.get("severity")) if payload.get("severity") else None,
        "category": _normalize_text(payload.get("category")) if payload.get("category") else None,
        "metric_keys": set(metrics.keys()),
        "occurred_at": _parse_event_time(payload.get("occurred_at")),
    }


def _score_operational_memory(memory: MemoryRecord, query: dict[str, Any]) -> dict[str, Any]:
    source_values = _source_values(memory)
    evidence_values = _evidence_values(memory)
    score = 0
    reasons: list[str] = []

    if query["service_name"] and query["service_name"] in source_values["service_name"]:
        score += 25
        reasons.append("same_service")
    if query["host_name"] and query["host_name"] in source_values["host_name"]:
        score += 20
        reasons.append("same_host")
    if query["environment"] and query["environment"] in source_values["environment"]:
        score += 15
        reasons.append("same_environment")
    if query["category"] and query["category"] in evidence_values.get("category", set()):
        score += 20
        reasons.append("same_alert_category")
    if query["severity"] and query["severity"] in source_values["severity"]:
        score += 10
        reasons.append("same_severity")

    overlapping_metric_keys = sorted(
        query["metric_keys"].intersection(evidence_values["metric_keys"])
    )
    if overlapping_metric_keys:
        score += min(10, 5 * len(overlapping_metric_keys))
        for key in overlapping_metric_keys[:2]:
            reasons.append(f"evidence_overlap:{key}")

    if memory.last_seen_at >= query["occurred_at"] - timedelta(days=7):
        score += 10
        reasons.append("recent_incident")

    return {
        "memory_id": str(memory.id),
        "memory_key": memory.memory_key,
        "summary": memory.summary,
        "score": min(score, 100),
        "reasons": reasons,
        "freshness": {
            "freshness_score": memory.freshness_score,
            "first_seen_at": memory.first_seen_at.isoformat(),
            "last_seen_at": memory.last_seen_at.isoformat(),
        },
        "provenance": _provenance_references(memory),
    }


def _is_meaningful_operational_match(result: dict[str, Any], query: dict[str, Any] | None = None) -> bool:
    """Exclude weak context-only matches from operational retrieval.

    Environment, severity, and recency help rank a candidate after there is a real
    operational anchor. Alone, they are too broad and create noisy false positives.
    """
    if query and query.get("service_name") is None and query.get("host_name") is None and query.get("category") is None and not query.get("metric_keys"):
        return True
    strong_reasons = {"same_service", "same_host", "same_alert_category"}
    return any(
        reason in strong_reasons or reason.startswith("evidence_overlap:")
        for reason in result["reasons"]
    )


def _source_values(memory: MemoryRecord) -> dict[str, set[Any]]:
    values: dict[str, set[Any]] = {
        "service_name": set(),
        "host_name": set(),
        "environment": set(),
        "severity": set(),
    }
    for link in memory.provenance_links:
        source = link.source_record
        values["service_name"].add(source.service_name)
        if source.host_name:
            values["host_name"].add(source.host_name)
        values["environment"].add(source.environment)
        values["severity"].add(source.severity)
    return values


def _evidence_values(memory: MemoryRecord) -> dict[str, set[Any]]:
    values: dict[str, set[Any]] = {"metric_keys": set()}
    for link in memory.provenance_links:
        evidence = link.evidence_record
        if evidence.evidence_type == "metric":
            values["metric_keys"].add(evidence.evidence_key)
        else:
            values.setdefault(evidence.evidence_key, set()).add(
                _normalize_text(evidence.evidence_value)
            )
    return values


def _provenance_references(memory: MemoryRecord, limit: int = 5) -> list[dict[str, Any]]:
    references = []
    seen: set[tuple[str, str]] = set()
    for link in sorted(
        memory.provenance_links,
        key=lambda item: (item.source_record.occurred_at, item.evidence_record.evidence_key),
        reverse=True,
    ):
        source = link.source_record
        evidence = link.evidence_record
        identity = (str(source.id), str(evidence.id))
        if identity in seen:
            continue
        seen.add(identity)
        references.append(
            {
                "source_record_id": str(source.id),
                "source_identifier": source.source_identifier,
                "source_type": source.source_type,
                "title": source.title,
                "severity": source.severity,
                "occurred_at": source.occurred_at.isoformat(),
                "evidence_record_id": str(evidence.id),
                "evidence_key": evidence.evidence_key,
                "evidence_value": evidence.evidence_value,
                "link_reason": link.link_reason,
            }
        )
        if len(references) >= limit:
            break
    return references
