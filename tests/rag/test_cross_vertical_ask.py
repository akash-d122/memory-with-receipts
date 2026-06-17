"""Integration tests for Cross-Vertical answer generation (RAG + Operational Memory)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.llm.generation import GenerationService
from memory_with_receipts.llm.mock import MockLLMProvider
from memory_with_receipts.memory.ingestion import ingest_operational_event
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.search_service import SearchService


def _setup_test_db():
    """Setup in-memory SQLite DB with RAG and Operational Memory schemas."""
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
    # 1. Seed operational active alert
    payload = {
        "source_type": "prometheus_alert",
        "source_identifier": "alertmanager:connections:postgres-prod:db-primary:1",
        "title": "PostgreSQL Max Connections Reached",
        "description": "Active client connections reached 98% of limit on db-primary.",
        "severity": "critical",
        "environment": "prod",
        "service_name": "postgres-prod",
        "host_name": "db-primary",
        "category": "connection_exhaustion",
        "metrics": {"active_connections": 490, "max_connections": 500},
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    ingest_operational_event(session, payload)

    # 2. Seed document runbook
    doc = Document(
        id=uuid.uuid4(),
        title="PostgreSQL Max Connections Runbook",
        source_type="markdown",
        uri="file:///docs/playbooks/connections.md",
        content_hash=Document.compute_content_hash("PostgreSQL Max Connections Runbook Content"),
        raw_content_text="Playbook steps to resolve connection exhaustion: kill idle transactions.",
        content_size_bytes=100,
        metadata_={},
    )
    session.add(doc)
    session.flush()

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=0,
        content="Playbook steps for high connections on db-primary: kill idle pids.",
        content_hash=Document.compute_content_hash("Playbook steps for high connections"),
        section_title="Connections Remediation",
        heading_path="# Playbooks > ## Connections Remediation",
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


def test_cross_vertical_ask_generates_citations_for_alert_and_playbook() -> None:
    """Test POST /v1/ask retrieves alert + playbook, LLM generates citations for both."""
    session = _setup_test_db()
    embedding_provider = MockEmbeddingProvider(dimension=384)
    _seed_data(session, embedding_provider)

    search_service = SearchService(embedding_provider=embedding_provider)
    llm_provider = MockLLMProvider()
    generation_service = GenerationService(
        llm_provider=llm_provider,
        search_service=search_service,
        default_top_k=5,
    )

    query = "too many connections on db-primary"
    result = generation_service.ask(session, query, top_k=5)

    assert result.is_insufficient is False
    assert result.context_chunks_used == 2

    # Verify LLM generation returned citations referencing both sources
    assert len(result.citations) == 2
    
    # Citation 1: Active Alert from Operational Memory
    assert result.citations[0].source_type == "operational-memory"
    expected_title = "prod:postgres-prod:db-primary:connection_exhaustion"
    assert expected_title in result.citations[0].document_title
    expected_uri = f"operational-memory://{expected_title}"
    assert result.citations[0].uri == expected_uri
    
    # Citation 2: Playbook Document
    assert result.citations[1].source_type == "markdown"
    assert result.citations[1].document_title == "PostgreSQL Max Connections Runbook"
    assert result.citations[1].uri == "file:///docs/playbooks/connections.md"
