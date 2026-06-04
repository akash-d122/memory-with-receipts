from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from memory_with_receipts.db.base import Base
from memory_with_receipts.memory.ingestion import ingest_operational_event
from memory_with_receipts.memory.operational_models import (
    EvidenceRecord,
    MemoryRecord,
    ProvenanceLink,
    SourceRecord,
)
from memory_with_receipts.retrieval.scoring import score_operational_memories


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    return session_factory()


def _replication_payload() -> dict:
    return {
        "source_type": "database_alarm",
        "source_identifier": (
            "alertmanager:replication-lag:postgres-prod:db-01:2026-05-20T08:00:00Z"
        ),
        "title": "Replication lag above threshold on postgres-prod",
        "description": "Replica db-01 is 184 seconds behind primary during backup window.",
        "severity": "critical",
        "environment": "prod",
        "service_name": "postgres-prod",
        "host_name": "db-01",
        "category": "replication_lag",
        "cluster": "postgres-prod-cluster",
        "metrics": {"replication_lag_seconds": 184},
        "runbook_ref": "runbooks/postgres/replication-lag.md",
        "remediation_note": "Check replica apply delay and backup IO contention.",
        "occurred_at": "2026-05-20T08:00:00Z",
    }


def test_operational_models_create_source_evidence_memory_and_provenance_graph():
    with _session() as session:
        source = SourceRecord(
            source_type="database_alarm",
            source_identifier="cpu-prod-db-02",
            title="DB CPU spike",
            description="CPU reached 97% on db-02",
            severity="warning",
            environment="prod",
            service_name="postgres-prod",
            host_name="db-02",
            raw_payload={"metrics": {"cpu_percent": 97}},
            occurred_at=datetime(2026, 5, 20, 8, 0, tzinfo=UTC),
        )
        evidence = EvidenceRecord(
            source_record=source,
            evidence_type="metric",
            evidence_key="cpu_percent",
            evidence_value=97,
            confidence_score=1.0,
        )
        memory = MemoryRecord(
            memory_key="prod:postgres-prod:db-02:high_cpu",
            summary="High CPU operational memory detected for postgres-prod on db-02.",
            memory_type="operational_incident_pattern",
            status="active",
            confidence_score=0.8,
            trust_score=0.5,
            freshness_score=1.0,
            contradiction_flag=False,
            first_seen_at=source.occurred_at,
            last_seen_at=source.occurred_at,
        )
        link = ProvenanceLink(
            memory_record=memory,
            source_record=source,
            evidence_record=evidence,
            link_reason="metric_supports_memory",
        )
        session.add(link)
        session.commit()

        stored_memory = session.scalars(select(MemoryRecord)).one()
        assert stored_memory.provenance_links[0].source_record.title == "DB CPU spike"
        assert stored_memory.provenance_links[0].evidence_record.evidence_key == "cpu_percent"


def test_ingest_operational_event_extracts_evidence_creates_memory_and_receipts():
    with _session() as session:
        result = ingest_operational_event(session, _replication_payload())

        assert result["memory_created"] is True
        assert result["memory_key"] == "prod:postgres-prod:db-01:replication_lag"
        assert result["evidence_count"] == 9
        assert result["provenance_link_count"] == 9

        source = session.scalars(select(SourceRecord)).one()
        assert source.raw_payload["metrics"]["replication_lag_seconds"] == 184

        evidence_by_key = {
            evidence.evidence_key: evidence.evidence_value
            for evidence in session.scalars(select(EvidenceRecord)).all()
        }
        assert evidence_by_key["replication_lag_seconds"] == 184
        assert evidence_by_key["category"] == "replication_lag"
        assert evidence_by_key["runbook_ref"] == "runbooks/postgres/replication-lag.md"
        assert (
            evidence_by_key["remediation_note"]
            == "Check replica apply delay and backup IO contention."
        )

        memory = session.scalars(select(MemoryRecord)).one()
        assert (
            memory.summary
            == "Replication lag operational memory detected for postgres-prod on db-01."
        )
        assert len(memory.provenance_links) == 9


def test_ingest_operational_event_updates_existing_memory_with_new_receipts():
    with _session() as session:
        first = ingest_operational_event(session, _replication_payload())
        second_payload = {
            **_replication_payload(),
            "source_identifier": (
                "alertmanager:replication-lag:postgres-prod:db-01:2026-05-20T08:05:00Z"
            ),
            "metrics": {"replication_lag_seconds": 210},
            "occurred_at": "2026-05-20T08:05:00Z",
        }
        second = ingest_operational_event(session, second_payload)

        assert first["memory_record_id"] == second["memory_record_id"]
        assert second["memory_created"] is False
        assert len(session.scalars(select(SourceRecord)).all()) == 2
        assert len(session.scalars(select(MemoryRecord)).all()) == 1
        assert len(session.scalars(select(ProvenanceLink)).all()) == 18

        memory = session.scalars(select(MemoryRecord)).one()
        assert memory.last_seen_at == datetime(2026, 5, 20, 8, 5, tzinfo=UTC)
        assert memory.trust_score > 0.5


def test_score_operational_memories_returns_explainable_deterministic_matches():
    with _session() as session:
        ingest_operational_event(session, _replication_payload())
        ingest_operational_event(
            session,
            {
                "source_type": "database_alarm",
                "source_identifier": "cloudwatch:cpu:analytics-db:db-09",
                "title": "CPU saturation on analytics DB",
                "description": "CPU reached 97%",
                "severity": "warning",
                "environment": "prod",
                "service_name": "analytics-db",
                "host_name": "db-09",
                "category": "high_cpu",
                "metrics": {"cpu_percent": 97},
                "occurred_at": "2026-05-18T10:00:00Z",
            },
        )

        results = score_operational_memories(
            session,
            {
                "severity": "critical",
                "environment": "prod",
                "service_name": "postgres-prod",
                "host_name": "db-01",
                "category": "replication_lag",
                "metrics": {"replication_lag_seconds": 120},
                "occurred_at": "2026-05-20T09:00:00Z",
            },
        )

        assert results[0]["score"] == 100
        assert results[0]["memory_key"] == "prod:postgres-prod:db-01:replication_lag"
        assert results[0]["reasons"] == [
            "same_service",
            "same_host",
            "same_environment",
            "same_alert_category",
            "same_severity",
            "evidence_overlap:replication_lag_seconds",
            "recent_incident",
        ]
        assert len(results) == 1


def test_score_operational_memories_does_not_return_recency_only_matches():
    with _session() as session:
        ingest_operational_event(
            session,
            {
                "source_type": "database_alarm",
                "source_identifier": "cloudwatch:cpu:analytics-db:db-09:2026-05-20T08:55:00Z",
                "title": "CPU saturation on analytics DB",
                "description": "CPU reached 97%",
                "severity": "warning",
                "environment": "prod",
                "service_name": "analytics-db",
                "host_name": "db-09",
                "category": "high_cpu",
                "metrics": {"cpu_percent": 97},
                "occurred_at": "2026-05-20T08:55:00Z",
            },
        )

        results = score_operational_memories(
            session,
            {
                "severity": "critical",
                "environment": "prod",
                "service_name": "postgres-prod",
                "host_name": "db-01",
                "category": "replication_lag",
                "metrics": {"replication_lag_seconds": 120},
                "occurred_at": "2026-05-20T09:00:00Z",
            },
        )

        assert results == []


def test_operational_ingestion_and_retrieval_emit_structured_logs(caplog):
    caplog.set_level("INFO")
    with _session() as session:
        payload = _replication_payload()
        ingest_operational_event(session, payload)
        score_operational_memories(session, payload)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "ingestion_started" in log_text
    assert "source_stored" in log_text
    assert "evidence_extracted" in log_text
    assert "memory_linked" in log_text
    assert "retrieval_scored" in log_text
