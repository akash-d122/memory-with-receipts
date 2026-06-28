"""Integration tests verifying the feedback loop from DBE diagnostics to Operational Memory and RAG."""

from __future__ import annotations

from unittest.mock import patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.api.app import create_app
from memory_with_receipts.api.dependencies import get_operational_db_session
from memory_with_receipts.api.rag_dependencies import get_rag_db_session
from memory_with_receipts.api.routes.dbe import get_dbe_llm_provider
from memory_with_receipts.db.base import Base
from memory_with_receipts.memory.operational_models import MemoryRecord, SourceRecord
from memory_with_receipts.rag.models import Document, Chunk
from memory_with_receipts.llm.mock import MockLLMProvider


def _test_app_with_shared_session():
    """Sets up a test app where both operational and RAG db sessions use the same in-memory SQLite db."""
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
    app.dependency_overrides[get_rag_db_session] = override_db_session
    return app, session_factory


def test_dbe_diagnose_creates_memory_and_rag_document():
    """Verify that triggering diagnosis automatically creates an operational memory event and indexes it as markdown."""
    app, session_factory = _test_app_with_shared_session()
    client = TestClient(app)

    # Configure a mock LLM provider returning a valid RCA Report
    canned_react = (
        "Thought: I need to investigate replication lag.\n"
        "Action: execute_sql(\"SELECT pg_last_wal_receive_lsn();\")\n"
        "Observation: 0/1628E10\n"
        "Thought: Replication is lagging. Creating report.\n"
        "RCA Report:\n"
        "# PostgreSQL Replication Lag Critical\n"
        "## Root Cause Analysis\n"
        "High write volume on primary database causing replica sync delay.\n"
        "## Preventative Recommendations\n"
        "Increase replication bandwidth.\n"
        "## Remediation Steps\n"
        "SELECT pg_reload_conf();"
    )
    mock_llm = MockLLMProvider(answer_template=canned_react)
    app.dependency_overrides[get_dbe_llm_provider] = lambda: mock_llm

    # Trigger diagnosis
    response = client.post(
        "/v1/dbe/diagnose",
        json={"query": "PostgreSQLReplicationLagCritical", "max_steps": 3},
        headers={"x-correlation-id": "test-dbe-correlation-unique"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["memory_id"] is not None
    assert data["document_id"] is not None
    assert data["is_successful"] is True

    # Validate database records
    with session_factory() as session:
        # Check Operational Memory event exists
        source = session.scalar(
            select(SourceRecord).where(SourceRecord.source_identifier == "dbe-test-dbe-correlation-unique")
        )
        assert source is not None
        assert source.source_type == "dbe-diagnostic"
        assert source.severity == "info"
        assert source.environment == "prod"
        assert source.service_name == "postgres"
        assert source.raw_payload["rca_report"] == data["rca_report"]

        # Check Operational Memory record is created
        mem = session.scalar(
            select(MemoryRecord).where(MemoryRecord.id == data["memory_id"])
        )
        assert mem is not None
        assert "replication_lag" in mem.memory_key

        # Check document RAG Document is created
        doc = session.scalar(
            select(Document).where(Document.id == data["document_id"])
        )
        assert doc is not None
        assert doc.title == "DBE RCA: PostgreSQLReplicationLagCritical"
        assert doc.source_type == "markdown"
        assert doc.uri == "dbe-rca://test-dbe-correlation-unique"

        # Check Document Chunks are populated
        chunks = session.scalars(
            select(Chunk).where(Chunk.document_id == doc.id)
        ).all()
        assert len(chunks) > 0
        assert any("High write volume on primary" in c.content for c in chunks)


def test_dbe_diagnose_idempotency_keeps_same_memory():
    """Verify that retrying a diagnose request with the same correlation ID is idempotent and returns the same memory_id."""
    app, session_factory = _test_app_with_shared_session()
    client = TestClient(app)

    canned_react = (
        "Thought: Checking replication status.\n"
        "RCA Report:\n"
        "# PostgreSQL Replication Lag Critical\n"
        "## Root Cause Analysis\n"
        "High lag.\n"
        "## Preventative Recommendations\n"
        "None.\n"
        "## Remediation Steps\n"
        "None."
    )
    mock_llm = MockLLMProvider(answer_template=canned_react)
    app.dependency_overrides[get_dbe_llm_provider] = lambda: mock_llm

    # Call first time
    r1 = client.post(
        "/v1/dbe/diagnose",
        json={"query": "PostgreSQLReplicationLagCritical", "max_steps": 2},
        headers={"x-correlation-id": "test-idempotent-1"}
    )
    assert r1.status_code == status.HTTP_200_OK
    d1 = r1.json()

    # Call second time with same correlation ID
    r2 = client.post(
        "/v1/dbe/diagnose",
        json={"query": "PostgreSQLReplicationLagCritical", "max_steps": 2},
        headers={"x-correlation-id": "test-idempotent-1"}
    )
    assert r2.status_code == status.HTTP_200_OK
    d2 = r2.json()

    # Verify that memory_id remains identical and no new Source/Memory records are duplicated
    assert d1["memory_id"] == d2["memory_id"]

    with session_factory() as session:
        sources = session.scalars(select(SourceRecord)).all()
        memories = session.scalars(select(MemoryRecord)).all()

        assert len(sources) == 1
        assert len(memories) == 1
