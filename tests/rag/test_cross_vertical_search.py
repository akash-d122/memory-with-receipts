"""Integration tests for Cross-Vertical search blending RAG and Operational Memory."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.memory.ingestion import ingest_operational_event
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.search_service import SearchService


def _setup_test_db():
    """Setup in-memory SQLite DB with clean schemas and session factory."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return SessionFactory()


def _seed_data(session, provider) -> None:
    # 1. Seed Operational Memory Event (Active Alert)
    payload = {
        "source_type": "prometheus_alert",
        "source_identifier": "alertmanager:lag:postgres-prod:db-replica-01:1",
        "title": "PostgreSQL Replication Lag Critical",
        "description": "Replication lag on db-replica-01 is extremely high at 12.4 GB.",
        "severity": "critical",
        "environment": "prod",
        "service_name": "postgres-prod",
        "host_name": "db-replica-01",
        "category": "replication_lag",
        "metrics": {"replication_lag_bytes": 13314398208},
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    ingest_operational_event(session, payload)

    # 2. Seed Document RAG Playbook Guide
    doc = Document(
        id=uuid.uuid4(),
        title="PostgreSQL Replication Playbook",
        source_type="markdown",
        uri="file:///docs/playbooks/replication.md",
        content_hash=Document.compute_content_hash("PostgreSQL Replication Playbook Content"),
        raw_content_text=(
            "Playbook steps to resolve replication lag: remove logical slot if inactive."
        ),
        content_size_bytes=100,
        metadata_={},
    )
    session.add(doc)
    session.flush()

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="Playbook steps to resolve replication lag on db-replica-01: check logical slots.",
        content_hash=Document.compute_content_hash("Playbook steps to resolve replication lag"),
        section_title="Lag Remediation",
        heading_path="# Replication > ## Lag Remediation",
        start_char=0,
        end_char=80,
        token_count=12,
        metadata_={},
    )
    session.add(chunk)
    session.flush()

    vector = provider.embed_single(chunk.content)
    emb = ChunkEmbedding(
        id=uuid.uuid4(),
        chunk_id=chunk.id,
        embedding=vector,
        embedding_model=provider.model_name,
        embedding_dimension=provider.dimension,
        embedding_provider=provider.provider_name,
        embedded_at=datetime.now(UTC),
    )
    session.add(emb)
    session.commit()


def test_blended_retrieval_returns_live_alert_and_playbook() -> None:
    """Test blended search (source_type=None) returns alert and runbook together."""
    session = _setup_test_db()
    provider = MockEmbeddingProvider(dimension=384)
    _seed_data(session, provider)

    service = SearchService(embedding_provider=provider)

    # Search query that matches service 'postgres-prod' and host 'db-replica-01'
    query = "replication lag on db-replica-01"
    results = service.search(session, query, top_k=5)

    assert len(results) >= 2
    # Verify blended context priority: operational memory (live alert) should be at rank 1
    assert results[0].source_type == "operational-memory"
    assert "prod:postgres-prod:db-replica-01:replication_lag" in results[0].document_title
    assert "Active Alert Summary" in results[0].content

    # Document RAG playbook should follow it
    assert results[1].source_type == "markdown"
    assert results[1].document_title == "PostgreSQL Replication Playbook"
    assert "Playbook steps" in results[1].content


def test_filtered_retrieval_respects_source_type() -> None:
    """Test filtering search by source_type limits results correctly."""
    session = _setup_test_db()
    provider = MockEmbeddingProvider(dimension=384)
    _seed_data(session, provider)

    service = SearchService(embedding_provider=provider)
    query = "replication lag on db-replica-01"

    # 1. Filter only operational memory
    results_op = service.search(session, query, source_type="operational-memory")
    assert len(results_op) == 1
    assert results_op[0].source_type == "operational-memory"

    # 2. Filter only playbooks (markdown)
    results_doc = service.search(session, query, source_type="markdown")
    assert len(results_doc) == 1
    assert results_doc[0].source_type == "markdown"
