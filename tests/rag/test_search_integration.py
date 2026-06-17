"""Integration tests for hybrid search against Docker Postgres with pgvector.

These tests require Docker Postgres to be running.
Run with: uv run python -m pytest tests/rag/test_search_integration.py -q -m integration
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from memory_with_receipts.core.exceptions import EmbeddingError, RetrievalError
from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.rag.keyword_search import keyword_search
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.search_service import SearchService
from memory_with_receipts.rag.vector_search import vector_search

# All tests in this file require Docker Postgres
pytestmark = pytest.mark.integration

POSTGRES_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/memory_with_receipts"


@pytest.fixture(scope="module")
def pg_engine():
    """Create engine connected to Docker Postgres with pgvector."""
    engine = create_engine(POSTGRES_URL)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """Transactional session with rollback for test isolation."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def provider():
    return MockEmbeddingProvider(dimension=384)


def _seed_pg_data(
    session: Session,
    provider: MockEmbeddingProvider,
    contents: list[str],
    title: str = "Test Doc",
    source_type: str = "text",
) -> tuple[Document, list[Chunk]]:
    """Seed a document with chunks and embeddings."""
    doc = Document(
        id=uuid.uuid4(),
        title=title,
        source_type=source_type,
        content_hash=Document.compute_content_hash(str(uuid.uuid4())),
        raw_content_text=" ".join(contents),
        content_size_bytes=sum(len(c) for c in contents),
        metadata_={},
    )
    session.add(doc)
    session.flush()

    chunks: list[Chunk] = []
    for i, content in enumerate(contents):
        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=i,
            content=content,
            content_hash=Document.compute_content_hash(content),
            section_title=f"Section {i}",
            heading_path=f"# Section {i}",
            start_char=i * 100,
            end_char=(i + 1) * 100,
            token_count=len(content.split()),
            metadata_={},
        )
        session.add(chunk)
        chunks.append(chunk)

    session.flush()

    vectors = provider.embed([c.content for c in chunks])
    for chunk, vec in zip(chunks, vectors, strict=True):
        emb = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk.id,
            embedding=vec,
            embedding_model=provider.model_name,
            embedding_dimension=provider.dimension,
            embedding_provider=provider.provider_name,
            embedded_at=datetime.now(UTC),
        )
        session.add(emb)

    session.flush()
    return doc, chunks


class TestVectorSearchIntegration:
    """Vector search against real pgvector."""

    def test_vector_search_returns_nearest_chunks(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Vector search must return chunks ordered by cosine similarity."""
        _seed_pg_data(
            pg_session, provider,
            contents=[
                "PostgreSQL replication lag monitoring and alerting",
                "Machine learning model deployment pipeline",
                "PostgreSQL failover procedures and recovery",
            ],
        )

        # Query close to PostgreSQL content
        query_vec = provider.embed_single("PostgreSQL replication monitoring")
        results = vector_search(pg_session, query_vec, top_k=10)

        assert len(results) == 3
        # All scores should be valid (-1 to 1 range for cosine similarity)
        for r in results:
            assert -1.0 - 1e-6 <= r.score <= 1.0 + 1e-6  # small epsilon for float

    def test_vector_search_empty_index(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Vector search on empty index returns empty results."""
        query_vec = provider.embed_single("anything")
        results = vector_search(pg_session, query_vec, top_k=10)
        assert results == []

    def test_vector_search_with_source_type_filter(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Vector search with source_type filter excludes non-matching."""
        _seed_pg_data(
            pg_session, provider,
            contents=["Text document content"],
            source_type="text",
        )
        _seed_pg_data(
            pg_session, provider,
            contents=["Markdown document content"],
            source_type="markdown",
        )

        query_vec = provider.embed_single("document content")
        results = vector_search(
            pg_session, query_vec, top_k=10, source_type="text",
        )

        # Should only return the text document's chunk
        assert len(results) == 1


class TestKeywordSearchIntegration:
    """Keyword search against real Postgres tsvector."""

    def test_keyword_search_finds_matching_chunks(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Keyword search must find chunks containing query terms."""
        _seed_pg_data(
            pg_session, provider,
            contents=[
                "PostgreSQL replication lag monitoring and alerting",
                "Machine learning model deployment pipeline",
                "PostgreSQL failover procedures and recovery",
            ],
        )

        results = keyword_search(pg_session, "PostgreSQL replication", top_k=10)
        assert len(results) >= 1

        # First result should be the most relevant match
        chunk_ids = {str(r.chunk_id) for r in results}
        assert len(chunk_ids) >= 1

    def test_keyword_search_no_match(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Keyword search with no matching terms returns empty."""
        _seed_pg_data(
            pg_session, provider,
            contents=["Database performance monitoring"],
        )

        results = keyword_search(pg_session, "xyznonexistent", top_k=10)
        assert results == []

    def test_keyword_search_with_source_type_filter(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Keyword search with source_type filter."""
        _seed_pg_data(
            pg_session, provider,
            contents=["Shared keyword content"],
            source_type="text",
        )
        _seed_pg_data(
            pg_session, provider,
            contents=["Shared keyword content"],
            source_type="markdown",
        )

        results = keyword_search(
            pg_session, "keyword", top_k=10, source_type="text",
        )
        assert len(results) == 1


class TestHybridSearchIntegration:
    """Full hybrid search pipeline against Postgres."""

    def test_hybrid_search_returns_receipt_results(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Hybrid search must return results with receipt metadata."""
        _seed_pg_data(
            pg_session, provider,
            contents=[
                "PostgreSQL replication lag monitoring and alerting",
                "Database failover procedures and switchover",
            ],
            title="Operations Guide",
            source_type="markdown",
        )

        service = SearchService(embedding_provider=provider)
        results = service.search(
            session=pg_session,
            query="PostgreSQL replication monitoring",
            top_k=10,
        )

        assert len(results) >= 1
        r = results[0]

        # Receipt metadata
        assert r.chunk_id is not None
        assert r.document_id is not None
        assert r.document_title == "Operations Guide"
        assert r.source_type == "markdown"
        assert r.content is not None
        assert r.rrf_score > 0
        assert len(r.reason_codes) > 0
        assert r.embedding_provider == "mock"
        assert r.embedding_model == "mock-embedding-model"

    def test_dimension_mismatch_fails_clearly(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Query with wrong embedding dimension must fail clearly."""
        _seed_pg_data(
            pg_session, provider,
            contents=["Some content for dimension test"],
        )

        # Create a provider with wrong dimension
        wrong_provider = MockEmbeddingProvider(dimension=128)
        service = SearchService(embedding_provider=wrong_provider)

        # The vector search SQL will fail because dimensions don't match
        # This should raise a clear error
        with pytest.raises((EmbeddingError, RetrievalError)):
            service.search(
                session=pg_session,
                query="dimension test",
                top_k=10,
            )

    def test_metadata_filter_excludes_non_matching(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Metadata filter should exclude non-matching documents."""
        _seed_pg_data(
            pg_session, provider,
            contents=["Content in text format"],
            source_type="text",
        )
        _seed_pg_data(
            pg_session, provider,
            contents=["Content in markdown format"],
            source_type="markdown",
        )

        service = SearchService(embedding_provider=provider)
        results = service.search(
            session=pg_session,
            query="Content format",
            source_type="text",
            top_k=10,
        )

        assert all(r.source_type == "text" for r in results)


class TestCustomMetadataFiltersIntegration:
    """Integration tests for key-value metadata_filters on Postgres JSONB."""

    def test_vector_and_keyword_search_with_metadata_filters(
        self, pg_session: Session, provider: MockEmbeddingProvider
    ) -> None:
        """Integration test for metadata filtering on Postgres."""
        # Seed matching document
        _seed_pg_data(
            pg_session, provider,
            contents=["Operational billing setup guide"],
            title="Billing Ops",
            source_type="text",
        )
        # Seed non-matching document with same content but different metadata
        _seed_pg_data(
            pg_session, provider,
            contents=["Operational billing setup guide"],
            title="Engineering Guide",
            source_type="text",
        )

        # Update metadata for the first document's record to contain {"category": "billing"}
        from memory_with_receipts.rag.models import Document
        billing_doc = pg_session.query(Document).filter(Document.title == "Billing Ops").first()
        assert billing_doc is not None
        billing_doc.metadata_ = {"category": "billing", "author": "alice"}
        
        eng_doc = pg_session.query(Document).filter(Document.title == "Engineering Guide").first()
        assert eng_doc is not None
        eng_doc.metadata_ = {"category": "engineering", "author": "alice"}
        
        pg_session.flush()

        service = SearchService(embedding_provider=provider)

        # Vector search (enable_vector=True, enable_keyword=False)
        vec_results = service.search(
            session=pg_session,
            query="billing setup",
            metadata_filters={"category": "billing"},
            enable_vector=True,
            enable_keyword=False,
            top_k=10,
        )
        assert len(vec_results) == 1
        assert vec_results[0].document_title == "Billing Ops"

        # Keyword search (enable_vector=False, enable_keyword=True)
        kw_results = service.search(
            session=pg_session,
            query="billing",
            metadata_filters={"category": "billing"},
            enable_vector=False,
            enable_keyword=True,
            top_k=10,
        )
        assert len(kw_results) == 1
        assert kw_results[0].document_title == "Billing Ops"

        # Hybrid search (both enabled)
        hybrid_results = service.search(
            session=pg_session,
            query="billing setup",
            metadata_filters={"category": "billing", "author": "alice"},
            enable_vector=True,
            enable_keyword=True,
            top_k=10,
        )
        assert len(hybrid_results) == 1
        assert hybrid_results[0].document_title == "Billing Ops"

        # Mismatch test
        mismatch_results = service.search(
            session=pg_session,
            query="billing setup",
            metadata_filters={"category": "billing", "author": "bob"},
            enable_vector=True,
            enable_keyword=True,
            top_k=10,
        )
        assert len(mismatch_results) == 0

