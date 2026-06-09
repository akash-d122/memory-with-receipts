"""API tests for POST /v1/search endpoint."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.api.app import create_app
from memory_with_receipts.api.routes.search import _get_rag_db_session, _get_search_service
from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.search_service import SearchService


def _test_app_with_search():
    """Create test app with in-memory SQLite and mock search service."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    # Import models so Base.metadata knows about them
    import memory_with_receipts.rag.models  # noqa: F401

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    provider = MockEmbeddingProvider(dimension=384)
    service = SearchService(embedding_provider=provider)

    app = create_app()

    def override_db_session():
        with session_factory() as session:
            yield session

    def override_search_service():
        return service

    app.dependency_overrides[_get_rag_db_session] = override_db_session
    app.dependency_overrides[_get_search_service] = override_search_service

    return app, session_factory, provider


def _seed_search_data(session_factory, provider):
    """Seed test data: one document with one embedded chunk."""
    with session_factory() as session:
        doc = Document(
            id=uuid.uuid4(),
            title="Failover Procedures",
            source_type="markdown",
            uri="file:///docs/failover.md",
            content_hash=Document.compute_content_hash("unique-content-" + str(uuid.uuid4())),
            raw_content_text="Detailed failover procedures for production databases.",
            content_size_bytes=100,
            metadata_={},
        )
        session.add(doc)
        session.flush()

        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content=(
                "Failover procedures for production PostgreSQL"
                " databases include automated switchover."
            ),
            content_hash=Document.compute_content_hash("failover-chunk"),
            section_title="Failover Steps",
            heading_path="# Failover > ## Steps",
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

    return doc, chunk


class TestSearchAPIEndpoint:
    """Tests for POST /v1/search."""

    def test_search_returns_200_with_results(self) -> None:
        """POST /v1/search must return 200 with search results."""
        app, session_factory, provider = _test_app_with_search()
        _seed_search_data(session_factory, provider)
        client = TestClient(app)

        response = client.post(
            "/v1/search",
            json={"query": "failover", "enable_vector": False, "enable_keyword": True},
            headers={"x-correlation-id": "search-test-1"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["correlation_id"] == "search-test-1"
        assert body["query"] == "failover"
        assert body["total_results"] >= 1
        assert body["retrieval_time_ms"] >= 0

    def test_search_empty_index_returns_empty_list(self) -> None:
        """POST /v1/search on empty index returns empty results, not error."""
        app, _factory, _provider = _test_app_with_search()
        client = TestClient(app)

        response = client.post(
            "/v1/search",
            json={"query": "nonexistent", "enable_vector": False, "enable_keyword": True},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total_results"] == 0
        assert body["results"] == []

    def test_search_validates_request_schema(self) -> None:
        """POST /v1/search rejects invalid request body."""
        app, _factory, _provider = _test_app_with_search()
        client = TestClient(app)

        # Missing required 'query' field
        response = client.post("/v1/search", json={})
        assert response.status_code == 422

    def test_search_validates_query_not_empty(self) -> None:
        """POST /v1/search rejects empty query string."""
        app, _factory, _provider = _test_app_with_search()
        client = TestClient(app)

        response = client.post("/v1/search", json={"query": ""})
        assert response.status_code == 422

    def test_search_result_has_receipt_metadata(self) -> None:
        """Every search result must include full receipt metadata."""
        app, session_factory, provider = _test_app_with_search()
        _seed_search_data(session_factory, provider)
        client = TestClient(app)

        response = client.post(
            "/v1/search",
            json={"query": "failover", "enable_vector": False, "enable_keyword": True},
        )

        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) >= 1

        r = results[0]
        # Identity
        assert r["chunk_id"] is not None
        assert r["document_id"] is not None
        assert r["document_title"] == "Failover Procedures"
        assert r["source_type"] == "markdown"
        assert r["uri"] == "file:///docs/failover.md"

        # Content
        assert r["chunk_index"] == 0
        assert "failover" in r["content"].lower()
        assert r["section_title"] is not None
        assert r["heading_path"] is not None
        assert r["start_char"] is not None
        assert r["end_char"] is not None

        # Scores
        assert r["rrf_score"] > 0
        assert isinstance(r["reason_codes"], list)
        assert len(r["reason_codes"]) > 0

        # Embedding metadata
        assert r["embedding_provider"] == "mock"
        assert r["embedding_model"] == "mock-embedding-model"

    def test_search_with_source_type_filter(self) -> None:
        """Source type filter excludes non-matching docs via API."""
        app, session_factory, provider = _test_app_with_search()
        _seed_search_data(session_factory, provider)
        client = TestClient(app)

        # Filter for 'text' but data is 'markdown' — should return empty
        response = client.post(
            "/v1/search",
            json={
                "query": "failover",
                "source_type": "text",
                "enable_vector": False,
                "enable_keyword": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["total_results"] == 0

    def test_search_top_k_limits_results(self) -> None:
        """top_k parameter must limit the number of results."""
        app, session_factory, provider = _test_app_with_search()

        # Seed multiple documents
        with session_factory() as session:
            for i in range(5):
                doc = Document(
                    id=uuid.uuid4(),
                    title=f"Doc {i}",
                    source_type="text",
                    content_hash=Document.compute_content_hash(f"unique-{i}-{uuid.uuid4()}"),
                    raw_content_text=f"Searchable content item {i}",
                    content_size_bytes=50,
                    metadata_={},
                )
                session.add(doc)
                session.flush()
                chunk = Chunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    chunk_index=0,
                    content=f"Searchable content item {i}",
                    content_hash=Document.compute_content_hash(f"chunk-{i}"),
                    start_char=0,
                    end_char=30,
                    token_count=5,
                    metadata_={},
                )
                session.add(chunk)
            session.commit()

        client = TestClient(app)
        response = client.post(
            "/v1/search",
            json={
                "query": "Searchable content",
                "top_k": 2,
                "enable_vector": False,
                "enable_keyword": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["total_results"] <= 2
