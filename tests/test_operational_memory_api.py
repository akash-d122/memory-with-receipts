from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.api.app import create_app
from memory_with_receipts.api.dependencies import get_operational_db_session
from memory_with_receipts.db.base import Base
from memory_with_receipts.memory.operational_models import (
    EvidenceRecord,
    MemoryRecord,
    ProvenanceLink,
    SourceRecord,
)


def _api_payload() -> dict:
    return {
        "source_type": "database_alarm",
        "source_identifier": "alertmanager:storage:postgres-prod:db-02:2026-05-20T09:00:00Z",
        "title": "Postgres storage saturation",
        "description": "Disk usage reached 91% on db-02.",
        "severity": "critical",
        "environment": "prod",
        "service_name": "postgres-prod",
        "host_name": "db-02",
        "category": "storage_saturation",
        "cluster": "postgres-prod-cluster",
        "metrics": {"disk_usage_percent": 91},
        "runbook_ref": "runbooks/postgres/storage.md",
        "remediation_note": "Check WAL growth and backup retention.",
        "occurred_at": "2026-05-20T09:00:00Z",
    }


def _test_app_with_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    app = create_app()

    def override_db_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_operational_db_session] = override_db_session
    return app, session_factory


def test_operational_ingestion_endpoint_is_idempotent_and_returns_correlation_id():
    from fastapi.testclient import TestClient

    app, session_factory = _test_app_with_session()
    client = TestClient(app)
    payload = _api_payload()

    first = client.post(
        "/operational-memory/events",
        json=payload,
        headers={"x-correlation-id": "test-correlation-1"},
    )
    second = client.post(
        "/operational-memory/events",
        json=payload,
        headers={"x-correlation-id": "test-correlation-2"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.headers["x-correlation-id"] == "test-correlation-1"
    assert second.headers["x-correlation-id"] == "test-correlation-2"

    first_body = first.json()
    second_body = second.json()
    assert first_body["idempotent_replay"] is False
    assert second_body["idempotent_replay"] is True
    assert second_body["source_record_id"] == first_body["source_record_id"]
    assert second_body["memory_record_id"] == first_body["memory_record_id"]
    assert second_body["evidence_count"] == first_body["evidence_count"]
    assert second_body["provenance_link_count"] == first_body["provenance_link_count"]

    with session_factory() as session:
        assert len(session.scalars(select(SourceRecord)).all()) == 1
        assert len(session.scalars(select(MemoryRecord)).all()) == 1
        assert len(session.scalars(select(EvidenceRecord)).all()) == first_body["evidence_count"]
        assert (
            len(session.scalars(select(ProvenanceLink)).all())
            == first_body["provenance_link_count"]
        )


def test_operational_retrieval_endpoint_returns_explanations_and_receipts():
    from fastapi.testclient import TestClient

    app, _session_factory = _test_app_with_session()
    client = TestClient(app)
    payload = _api_payload()
    client.post("/operational-memory/events", json=payload)

    response = client.post(
        "/operational-memory/retrieval",
        json={
            "severity": "critical",
            "environment": "prod",
            "service_name": "postgres-prod",
            "host_name": "db-02",
            "category": "storage_saturation",
            "metrics": {"disk_usage_percent": 95},
            "occurred_at": "2026-05-20T09:30:00Z",
            "limit": 5,
        },
        headers={"x-correlation-id": "retrieval-correlation"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["correlation_id"] == "retrieval-correlation"
    assert len(body["matched_memories"]) == 1

    match = body["matched_memories"][0]
    assert match["score"] == 100
    assert match["reasons"] == [
        "same_service",
        "same_host",
        "same_environment",
        "same_alert_category",
        "same_severity",
        "evidence_overlap:disk_usage_percent",
        "recent_incident",
    ]
    assert match["freshness"]["freshness_score"] == 1.0
    assert match["provenance"]
    assert match["provenance"][0]["source_identifier"] == payload["source_identifier"]


def test_operational_ingestion_endpoint_rejects_invalid_payloads_deterministically():
    from fastapi.testclient import TestClient

    app, _session_factory = _test_app_with_session()
    client = TestClient(app)

    response = client.post(
        "/operational-memory/events",
        json={"source_type": "database_alarm"},
        headers={"x-correlation-id": "invalid-payload-correlation"},
    )

    assert response.status_code == 422
    assert response.headers["x-correlation-id"] == "invalid-payload-correlation"
    detail = response.json()["detail"]
    assert detail["error"] == "request_validation_failed"
    assert detail["correlation_id"] == "invalid-payload-correlation"
    assert detail["fields"]


def test_duplicate_ingestion_does_not_inflate_memory_trust_score():
    from memory_with_receipts.memory.ingestion import ingest_operational_event

    app, session_factory = _test_app_with_session()
    _ = app
    payload = _api_payload()

    with session_factory() as session:
        first = ingest_operational_event(session, payload)
        memory_after_first = session.get(MemoryRecord, first["memory_record_id"])
        assert memory_after_first is not None
        trust_after_first = memory_after_first.trust_score

        replay = ingest_operational_event(session, payload)
        memory_after_replay = session.get(MemoryRecord, first["memory_record_id"])
        assert memory_after_replay is not None

        assert replay["idempotent_replay"] is True
        assert memory_after_replay.trust_score == trust_after_first
        assert len(session.scalars(select(SourceRecord)).all()) == 1
        assert len(session.scalars(select(MemoryRecord)).all()) == 1
