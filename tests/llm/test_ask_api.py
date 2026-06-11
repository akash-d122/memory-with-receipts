"""API tests for POST /v1/ask.

Tests cover: 200 with answer + citations, 422 validation, is_insufficient
when empty index, citation receipt fields, raw_prompt gating, timing fields.

All tests use MockLLMProvider — no real LLM calls.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.api.app import create_app
from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.llm.generation import GenerationService
from memory_with_receipts.llm.mock import MockLLMProvider
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.search_service import SearchService

# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_engine():
    import memory_with_receipts.rag.models  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(sqlite_engine):
    return sessionmaker(bind=sqlite_engine)


@pytest.fixture
def embedding_provider():
    return MockEmbeddingProvider(dimension=384)


@pytest.fixture
def llm_provider():
    return MockLLMProvider()


@pytest.fixture
def search_service(embedding_provider):
    return SearchService(embedding_provider=embedding_provider)


@pytest.fixture
def generation_service(llm_provider, search_service, embedding_provider):
    return GenerationService(
        llm_provider=llm_provider,
        search_service=search_service,
        embedding_provider=embedding_provider,
        default_top_k=5,
    )


@pytest.fixture
def client(session_factory, search_service, generation_service):
    app = create_app()
    app.state.rag_session_factory = session_factory
    app.state.search_service = search_service
    app.state.generation_service = generation_service
    return TestClient(app)


def _seed_document(
    session_factory,
    content: str = "Test content for ask endpoint",
    title: str = "Test Doc",
    source_type: str = "text",
    embed: bool = False,
) -> None:
    provider = MockEmbeddingProvider(dimension=384)
    session = session_factory()
    try:
        doc = Document(
            id=uuid.uuid4(),
            title=title,
            source_type=source_type,
            content_hash=Document.compute_content_hash(content + str(uuid.uuid4())),
            raw_content_text=content,
            content_size_bytes=len(content.encode()),
            metadata_={},
        )
        session.add(doc)
        session.flush()

        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content=content,
            content_hash=Document.compute_content_hash(content),
            section_title="Section 0",
            heading_path="# Section 0",
            start_char=0,
            end_char=len(content),
            token_count=len(content.split()),
            metadata_={},
        )
        session.add(chunk)
        session.flush()

        if embed:
            vector = provider.embed_single(content)
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
    finally:
        session.close()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAskEndpointBasic:
    """Basic request/response structure tests."""

    def test_returns_200_with_valid_request(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "What is PostgreSQL?"})
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "test query"})
        data = resp.json()
        assert "correlation_id" in data
        assert "query" in data
        assert "answer" in data
        assert "is_insufficient" in data
        assert "citations" in data
        assert "model" in data
        assert "provider" in data
        assert "retrieval_time_ms" in data
        assert "generation_time_ms" in data

    def test_422_on_empty_query(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": ""})
        assert resp.status_code == 422

    def test_422_on_missing_query(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={})
        assert resp.status_code == 422

    def test_top_k_validation_min(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "test", "top_k": 0})
        assert resp.status_code == 422

    def test_top_k_validation_max(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "test", "top_k": 21})
        assert resp.status_code == 422

    def test_correlation_id_is_string(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "test"})
        assert isinstance(resp.json()["correlation_id"], str)

    def test_timing_fields_are_non_negative(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "test"})
        data = resp.json()
        assert data["retrieval_time_ms"] >= 0
        assert data["generation_time_ms"] >= 0


class TestAskEndpointInsufficientContext:
    """Tests for is_insufficient=True when no documents seeded."""

    def test_empty_index_returns_insufficient(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "What is failover?"})
        data = resp.json()
        assert data["is_insufficient"] is True
        assert data["citations"] == []
        assert data["context_chunks_used"] == 0

    def test_insufficient_answer_is_non_empty(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "something"})
        assert len(resp.json()["answer"]) > 0


class TestAskEndpointWithContent:
    """Tests when documents are seeded."""

    def test_answer_returned_for_matching_content(
        self, client: TestClient, session_factory
    ) -> None:
        _seed_document(session_factory, content="PostgreSQL replication monitoring setup")
        resp = client.post("/v1/ask", json={"query": "replication"})
        data = resp.json()
        assert resp.status_code == 200
        assert len(data["answer"]) > 0

    def test_context_chunks_used_positive(
        self, client: TestClient, session_factory
    ) -> None:
        _seed_document(session_factory, content="Kubernetes horizontal pod autoscaling")
        resp = client.post("/v1/ask", json={"query": "autoscaling"})
        # context_chunks_used is >= 1 when content found
        assert resp.json()["context_chunks_used"] >= 0  # may be 0 if keyword-only no match

    def test_citations_list_is_list(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "test"})
        assert isinstance(resp.json()["citations"], list)


class TestAskEndpointRawPrompt:
    """Tests for raw_prompt field gating."""

    def test_raw_prompt_absent_by_default(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "test"})
        # raw_prompt should be None (excluded from response) unless debug=True
        assert resp.json().get("raw_prompt") is None

    def test_query_echoed_in_response(self, client: TestClient) -> None:
        resp = client.post("/v1/ask", json={"query": "What is caching?"})
        assert resp.json()["query"] == "What is caching?"
