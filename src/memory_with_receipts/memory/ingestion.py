from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from memory_with_receipts.memory.operational_models import (
    EvidenceRecord,
    MemoryRecord,
    ProvenanceLink,
    SourceRecord,
)

logger = logging.getLogger("memory_with_receipts.operational_memory")

DIMENSION_KEYS = (
    "category",
    "cluster",
    "severity",
    "environment",
    "service_name",
    "host_name",
    "runbook_ref",
    "remediation_note",
)

CATEGORY_LABELS = {
    "replication_lag": "Replication lag",
    "high_cpu": "High CPU",
    "failover_detected": "Failover",
    "storage_saturation": "Storage saturation",
    "deadlock_spike": "Deadlock spike",
    "connection_exhaustion": "Connection exhaustion",
}


def ingest_operational_event(
    session: Session, payload: dict[str, Any], correlation_id: str | None = None
) -> dict[str, Any]:
    """Ingest one structured DB operational event using deterministic extraction only.

    Idempotency is intentionally strict: source_identifier is the operational event identity.
    Duplicate/retried events return the already-stored source/memory/provenance graph without
    creating new evidence or inflating memory trust.
    """
    _log(
        "ingestion_started",
        correlation_id=correlation_id,
        source_identifier=payload.get("source_identifier"),
        category=payload.get("category"),
    )

    _validate_payload(payload)

    existing_source = _find_source_with_receipts(session, str(payload["source_identifier"]))
    if existing_source is not None:
        result = _existing_ingestion_result(existing_source)
        _log(
            "ingestion_idempotent_replay",
            correlation_id=correlation_id,
            source_record_id=result["source_record_id"],
            source_identifier=existing_source.source_identifier,
            memory_record_id=result["memory_record_id"],
            provenance_link_count=result["provenance_link_count"],
        )
        return result

    occurred_at = _parse_event_time(payload.get("occurred_at"))
    now = datetime.now(UTC)

    source = SourceRecord(
        source_type=str(payload["source_type"]),
        source_identifier=str(payload["source_identifier"]),
        title=str(payload["title"]),
        description=str(payload.get("description") or ""),
        severity=_normalize_text(payload["severity"]),
        environment=_normalize_text(payload["environment"]),
        service_name=str(payload["service_name"]),
        host_name=str(payload["host_name"]) if payload.get("host_name") else None,
        raw_payload=dict(payload),
        occurred_at=occurred_at,
        ingested_at=now,
    )
    session.add(source)
    try:
        session.flush()
    except IntegrityError:
        # Race-safe fallback: another transaction inserted the same source_identifier first.
        session.rollback()
        existing_source = _find_source_with_receipts(session, str(payload["source_identifier"]))
        if existing_source is None:
            _log(
                "ingestion_failed_after_integrity_error",
                correlation_id=correlation_id,
                source_identifier=payload.get("source_identifier"),
            )
            raise
        result = _existing_ingestion_result(existing_source)
        _log(
            "ingestion_idempotent_replay_after_race",
            correlation_id=correlation_id,
            source_record_id=result["source_record_id"],
            source_identifier=existing_source.source_identifier,
            memory_record_id=result["memory_record_id"],
        )
        return result

    _log(
        "source_stored",
        correlation_id=correlation_id,
        source_record_id=str(source.id),
        source_identifier=source.source_identifier,
    )

    evidence_records = [
        EvidenceRecord(
            source_record=source,
            evidence_type=evidence_type,
            evidence_key=evidence_key,
            evidence_value=evidence_value,
            confidence_score=confidence_score,
            extracted_at=now,
        )
        for evidence_type, evidence_key, evidence_value, confidence_score in _extract_evidence(
            payload
        )
    ]
    session.add_all(evidence_records)
    session.flush()
    _log(
        "evidence_extracted",
        correlation_id=correlation_id,
        source_record_id=str(source.id),
        evidence_count=len(evidence_records),
    )

    memory_key = build_operational_memory_key(payload)
    memory = session.scalar(select(MemoryRecord).where(MemoryRecord.memory_key == memory_key))
    memory_created = memory is None
    if memory is None:
        memory = MemoryRecord(
            memory_key=memory_key,
            summary=build_operational_memory_summary(payload),
            memory_type="operational_incident_pattern",
            status="active",
            confidence_score=0.8,
            trust_score=0.5,
            freshness_score=1.0,
            contradiction_flag=False,
            first_seen_at=occurred_at,
            last_seen_at=occurred_at,
        )
        session.add(memory)
        session.flush()
    else:
        memory.last_seen_at = max(memory.last_seen_at, occurred_at)
        memory.freshness_score = 1.0
        memory.trust_score = min(1.0, memory.trust_score + 0.1)
        memory.confidence_score = min(1.0, memory.confidence_score + 0.03)
        memory.summary = build_operational_memory_summary(payload)

    links = [
        ProvenanceLink(
            memory_record=memory,
            source_record=source,
            evidence_record=evidence,
            link_reason=_link_reason_for(evidence),
            created_at=now,
        )
        for evidence in evidence_records
    ]
    session.add_all(links)
    session.commit()

    _log(
        "memory_linked",
        correlation_id=correlation_id,
        memory_record_id=str(memory.id),
        memory_key=memory.memory_key,
        memory_created=memory_created,
        provenance_link_count=len(links),
    )

    return {
        "source_record_id": str(source.id),
        "memory_record_id": str(memory.id),
        "memory_key": memory.memory_key,
        "memory_created": memory_created,
        "idempotent_replay": False,
        "evidence_count": len(evidence_records),
        "provenance_link_count": len(links),
    }


def build_operational_memory_key(payload: dict[str, Any]) -> str:
    environment = _normalize_text(payload.get("environment"))
    service = _normalize_text(payload.get("service_name"))
    subject = _normalize_text(payload.get("host_name") or payload.get("cluster") or "service")
    category = _normalize_text(payload.get("category"))
    return f"{environment}:{service}:{subject}:{category}"


def build_operational_memory_summary(payload: dict[str, Any]) -> str:
    category = _normalize_text(payload.get("category"))
    service = str(payload.get("service_name"))
    subject = payload.get("host_name") or payload.get("cluster") or service
    label = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
    return f"{label} operational memory detected for {service} on {subject}."


def _extract_evidence(payload: dict[str, Any]) -> list[tuple[str, str, Any, float]]:
    evidence: list[tuple[str, str, Any, float]] = []

    for key in DIMENSION_KEYS:
        value = payload.get(key)
        if value not in (None, ""):
            evidence.append(("dimension", key, value, 0.95))

    metrics = payload.get("metrics") or {}
    if not isinstance(metrics, dict):
        raise ValueError("payload.metrics must be a dictionary when provided")

    for metric_key in sorted(metrics):
        metric_value = metrics[metric_key]
        if metric_value is not None:
            evidence.append(("metric", metric_key, metric_value, 1.0))

    return evidence


def _validate_payload(payload: dict[str, Any]) -> None:
    required = [
        "source_type",
        "source_identifier",
        "title",
        "severity",
        "environment",
        "service_name",
        "category",
    ]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise ValueError(f"Missing required operational event fields: {', '.join(missing)}")


def _parse_event_time(value: Any | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _normalize_text(value: Any | None, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip().lower().replace(" ", "_")
    return text or default


def _link_reason_for(evidence: EvidenceRecord) -> str:
    if evidence.evidence_type == "metric":
        return "metric_supports_memory"
    return "dimension_supports_memory"


def _find_source_with_receipts(session: Session, source_identifier: str) -> SourceRecord | None:
    return session.scalar(
        select(SourceRecord)
        .where(SourceRecord.source_identifier == source_identifier)
        .options(
            selectinload(SourceRecord.evidence_records),
            selectinload(SourceRecord.provenance_links).selectinload(ProvenanceLink.memory_record),
        )
    )


def _existing_ingestion_result(source: SourceRecord) -> dict[str, Any]:
    memory = None
    if source.provenance_links:
        memory = source.provenance_links[0].memory_record

    return {
        "source_record_id": str(source.id),
        "memory_record_id": str(memory.id) if memory else None,
        "memory_key": memory.memory_key if memory else None,
        "memory_created": False,
        "idempotent_replay": True,
        "evidence_count": len(source.evidence_records),
        "provenance_link_count": len(source.provenance_links),
    }


def _log(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True, default=str))
