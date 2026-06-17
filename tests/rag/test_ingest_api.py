"""API integration tests for document ingestion endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.api.app import create_app
from memory_with_receipts.api.rag_dependencies import get_ingestion_pipeline, get_rag_db_session
from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.ingestion.chunking.structure_aware import StructureAwareChunker
from memory_with_receipts.ingestion.parsers.json_parser import JSONParser
from memory_with_receipts.ingestion.parsers.markdown_parser import MarkdownParser
from memory_with_receipts.ingestion.parsers.pdf_parser import PDFParser
from memory_with_receipts.ingestion.parsers.text_parser import TextParser
from memory_with_receipts.ingestion.parsers.web_parser import WebParser
from memory_with_receipts.ingestion.pipeline import IngestionPipeline
from memory_with_receipts.rag.models import Document


def _setup_test_app():
    """Build test app with in-memory SQLite and customized pipeline dependencies."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    # Import models to ensure they are registered with Base.metadata
    import memory_with_receipts.rag.models  # noqa: F401

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    provider = MockEmbeddingProvider(dimension=384)
    chunker = StructureAwareChunker(chunk_size=50)  # small chunk size for testing

    parsers = [
        MarkdownParser(),
        TextParser(),
        PDFParser(),
        WebParser(),
        JSONParser(),
    ]
    pipeline = IngestionPipeline(
        parsers=parsers,
        chunker=chunker,
        embedding_provider=provider,
    )

    app = create_app()

    def override_db_session():
        with session_factory() as session:
            yield session

    def override_pipeline():
        return pipeline

    app.dependency_overrides[get_rag_db_session] = override_db_session
    app.dependency_overrides[get_ingestion_pipeline] = override_pipeline

    return app, session_factory


def test_ingest_json_success() -> None:
    """Test POST /v1/ingest with a raw JSON request."""
    app, session_factory = _setup_test_app()
    client = TestClient(app)

    payload = {
        "title": "Database Read Replicas",
        "content": (
            "# DB Read Replicas\n\n"
            "Read replicas allow offloading read traffic from the primary."
        ),
        "source_type": "markdown",
        "uri": "wiki://read-replicas",
        "tags": "db,replica,ops",
        "metadata": {"author": "SRE Team"},
    }

    response = client.post("/v1/ingest", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "Database Read Replicas"
    assert data["source_type"] == "markdown"
    assert data["is_duplicate"] is False
    assert data["chunk_count"] > 0
    assert data["embeddings_created"] == data["chunk_count"]
    assert "document_id" in data
    assert "correlation_id" in data

    # Verify DB state
    with session_factory() as session:
        doc = session.query(Document).filter(Document.title == "Database Read Replicas").first()
        assert doc is not None
        assert doc.source_type == "markdown"
        assert doc.metadata_["author"] == "SRE Team"
        assert doc.metadata_["tags"] == "db,replica,ops"


def test_ingest_json_deduplication() -> None:
    """Test duplicate JSON ingestions return is_duplicate=True and don't re-embed."""
    app, _ = _setup_test_app()
    client = TestClient(app)

    payload = {
        "title": "PostgreSQL Backup SOP",
        "content": "Perform weekly backup using pg_dumpall tool.",
        "source_type": "text",
    }

    # First Ingest
    res1 = client.post("/v1/ingest", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["is_duplicate"] is False
    doc_id = data1["document_id"]

    # Second Ingest (Duplicate Content)
    res2 = client.post("/v1/ingest", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["is_duplicate"] is True
    assert data2["document_id"] == doc_id
    assert data2["embeddings_created"] == 0


def test_ingest_file_upload_detect_extension() -> None:
    """Test POST /v1/ingest/file with auto extension routing."""
    app, session_factory = _setup_test_app()
    client = TestClient(app)

    file_content = b"# Failover Runbook\n\nRun pg_ctl promote on replica."
    file_payload = {"file": ("failover_guide.md", file_content, "text/markdown")}

    response = client.post(
        "/v1/ingest/file",
        files=file_payload,
        data={"tags": "runbook,postgres"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "failover_guide.md"
    assert data["source_type"] == "markdown"  # correctly detected
    assert data["is_duplicate"] is False
    assert data["chunk_count"] > 0

    with session_factory() as session:
        doc = session.query(Document).filter(Document.title == "failover_guide.md").first()
        assert doc is not None
        assert doc.metadata_["tags"] == "runbook,postgres"


def test_ingest_file_upload_form_overrides() -> None:
    """Test POST /v1/ingest/file with explicit form-data title/type overrides."""
    app, session_factory = _setup_test_app()
    client = TestClient(app)

    file_content = b"Some random logs contents"
    file_payload = {"file": ("logs.txt", file_content, "text/plain")}

    response = client.post(
        "/v1/ingest/file",
        files=file_payload,
        data={
            "title": "Production Logs Audit",
            "source_type": "text",
            "uri": "s3://logs/prod-audit.log",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "Production Logs Audit"
    assert data["source_type"] == "text"
    assert data["is_duplicate"] is False

    with session_factory() as session:
        doc = session.query(Document).filter(Document.title == "Production Logs Audit").first()
        assert doc is not None
        assert doc.uri == "s3://logs/prod-audit.log"


def test_ingest_prometheus_webhook_single() -> None:
    """Test POST /v1/ingest/webhook/prometheus with single alert payload."""
    app, session_factory = _setup_test_app()
    client = TestClient(app)

    webhook_payload = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "PostgreSQLMaxConnectionsReached",
                    "severity": "critical",
                    "instance": "db-primary.prod.internal:5432",
                    "database": "production_db",
                    "extra_label_test": "123",
                },
                "annotations": {
                    "summary": "Active connections reached 96% of limit",
                    "description": "480 active connections out of 500 max.",
                },
                "startsAt": "2026-06-15T16:00:00Z",
                "generatorURL": "http://prometheus:9090/graph",
            }
        ],
    }

    response = client.post("/v1/ingest/webhook/prometheus", json=webhook_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["alerts_processed"] == 1
    assert len(data["results"]) == 1

    result = data["results"][0]
    assert result["title"] == "Prometheus Alert: PostgreSQLMaxConnectionsReached"
    assert result["source_type"] == "markdown"
    assert result["is_duplicate"] is False

    # Check database document details
    with session_factory() as session:
        doc = (
            session.query(Document)
            .filter(Document.title == "Prometheus Alert: PostgreSQLMaxConnectionsReached")
            .first()
        )
        assert doc is not None
        assert doc.metadata_["source"] == "prometheus-webhook"
        assert doc.metadata_["type"] == "prometheus-alert"
        assert doc.metadata_["alertname"] == "PostgreSQLMaxConnectionsReached"
        assert doc.metadata_["severity"] == "critical"
        assert doc.metadata_["instance"] == "db-primary.prod.internal:5432"
        assert doc.metadata_["extra_label_test"] == "123"

        # Check raw markdown format was built correctly
        content = doc.raw_content_text
        assert "# Prometheus Alert: PostgreSQLMaxConnectionsReached" in content
        assert "Active connections reached 96% of limit" in content
        assert "480 active connections out of 500 max." in content
        assert "db-primary.prod.internal:5432" in content
        assert "extra_label_test" in content
