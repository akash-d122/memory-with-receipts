"""Integration tests for pgvector embedding storage.

These tests require Docker Postgres with pgvector to be running.
Run with: uv run python -m pytest tests/rag/test_embedding_storage_integration.py -q -m integration

All tests use synchronous psycopg for simpler fixtures. Each test runs
in a savepoint that's rolled back to keep the DB clean.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document

# All tests in this file require Docker Postgres
pytestmark = pytest.mark.integration

# Synchronous psycopg URL for test simplicity
POSTGRES_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/memory_with_receipts"


@pytest.fixture(scope="module")
def pg_engine():
    """Create a synchronous engine connected to the Docker Postgres instance."""
    engine = create_engine(POSTGRES_URL)

    # Enable pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Drop existing tables to ensure we start fresh under test environment settings
    Base.metadata.drop_all(engine)

    # Create all tables (including chunk_embeddings with pgvector)
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup: drop tables in reverse dependency order
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """Provide a transactional session using nested savepoints.

    Uses begin_nested() so that even tests causing DB errors can
    roll back cleanly without breaking the outer transaction.
    """
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


def _create_test_document(session: Session) -> Document:
    """Helper to create a test document."""
    doc = Document(
        id=uuid.uuid4(),
        title="Test Document",
        source_type="text",
        content_hash=Document.compute_content_hash(f"test content {uuid.uuid4()}"),
        raw_content_text="test content",
        content_size_bytes=12,
    )
    session.add(doc)
    session.flush()
    return doc


def _create_test_chunk(session: Session, doc: Document, index: int = 0) -> Chunk:
    """Helper to create a test chunk."""
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        chunk_index=index,
        content=f"Test chunk content {index}",
        content_hash=Document.compute_content_hash(f"Test chunk content {index} {uuid.uuid4()}"),
        start_char=0,
        end_char=20,
        token_count=5,
    )
    session.add(chunk)
    session.flush()
    return chunk


class TestPgvectorExtension:
    """Tests that pgvector is enabled and functional."""

    def test_pgvector_extension_enabled(self, pg_session: Session) -> None:
        """pgvector extension must be installed in the database."""
        result = pg_session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
        assert result is not None
        assert result[0] == "vector"


class TestChunkEmbeddingInsert:
    """Tests for inserting and reading chunk embeddings with pgvector."""

    def test_chunk_embedding_insert(self, pg_session: Session) -> None:
        """Can insert a ChunkEmbedding row with a real pgvector vector."""
        doc = _create_test_document(pg_session)
        chunk = _create_test_chunk(pg_session, doc)

        provider = MockEmbeddingProvider(dimension=384)
        vector = provider.embed_single("test content")

        embedding = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk.id,
            embedding=vector,
            embedding_model=provider.model_name,
            embedding_dimension=provider.dimension,
            embedding_provider=provider.provider_name,
            embedded_at=datetime.now(UTC),
        )
        pg_session.add(embedding)
        pg_session.flush()

        # Read it back
        loaded = pg_session.get(ChunkEmbedding, embedding.id)
        assert loaded is not None
        assert len(loaded.embedding) == 384

    def test_chunk_embedding_stores_metadata(self, pg_session: Session) -> None:
        """All metadata fields must be stored and retrievable."""
        doc = _create_test_document(pg_session)
        chunk = _create_test_chunk(pg_session, doc)

        provider = MockEmbeddingProvider(dimension=384)
        vector = provider.embed_single("metadata test")
        now = datetime.now(UTC)

        embedding = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk.id,
            embedding=vector,
            embedding_model="test-model-v1",
            embedding_dimension=384,
            embedding_provider="mock",
            embedded_at=now,
        )
        pg_session.add(embedding)
        pg_session.flush()

        loaded = pg_session.get(ChunkEmbedding, embedding.id)
        assert loaded is not None
        assert loaded.embedding_model == "test-model-v1"
        assert loaded.embedding_dimension == 384
        assert loaded.embedding_provider == "mock"
        assert loaded.embedded_at is not None

    def test_embedding_dimension_mismatch_insert_fails(
        self, pg_session: Session
    ) -> None:
        """Inserting a vector with wrong dimension must raise a DB error."""
        doc = _create_test_document(pg_session)
        chunk = _create_test_chunk(pg_session, doc)

        # Create a 128-dim vector for a 384-dim column
        wrong_vector = [0.1] * 128

        embedding = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk.id,
            embedding=wrong_vector,
            embedding_model="wrong-dim-model",
            embedding_dimension=128,
            embedding_provider="mock",
            embedded_at=datetime.now(UTC),
        )

        # Use a savepoint so the DB error doesn't break the outer transaction
        nested = pg_session.begin_nested()
        pg_session.add(embedding)
        with pytest.raises(Exception):  # noqa: B017
            pg_session.flush()
        nested.rollback()


class TestVectorSimilarityOrdering:
    """Tests for vector similarity search using pgvector cosine distance."""

    def test_vector_similarity_ordering(self, pg_session: Session) -> None:
        """Cosine distance ordering must return the closest vector first."""
        doc = _create_test_document(pg_session)

        # Create three chunks with distinct embeddings
        provider = MockEmbeddingProvider(dimension=384)

        texts = [
            "machine learning algorithms",
            "deep learning neural networks",
            "cooking recipes for dinner",
        ]

        chunks = []
        for i, t in enumerate(texts):
            chunk = _create_test_chunk(pg_session, doc, index=i)
            chunks.append(chunk)

            vector = provider.embed_single(t)
            embedding = ChunkEmbedding(
                id=uuid.uuid4(),
                chunk_id=chunk.id,
                embedding=vector,
                embedding_model=provider.model_name,
                embedding_dimension=provider.dimension,
                embedding_provider=provider.provider_name,
                embedded_at=datetime.now(UTC),
            )
            pg_session.add(embedding)

        pg_session.flush()

        # Query: find chunks closest to "machine learning algorithms"
        query_vector = provider.embed_single("machine learning algorithms")
        query_vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        # Use cosine distance operator (<=>)
        # Use CAST() instead of :: to avoid psycopg named-parameter syntax conflict
        results = pg_session.execute(
            text(
                "SELECT ce.chunk_id, ce.embedding <=> CAST(:query_vec AS vector) AS distance "
                "FROM chunk_embeddings ce "
                "ORDER BY distance ASC"
            ),
            {"query_vec": query_vector_str},
        ).fetchall()

        assert len(results) == 3

        # The first result should be the exact match (distance ≈ 0)
        first_chunk_id = results[0][0]
        first_distance = results[0][1]

        assert first_chunk_id == chunks[0].id
        assert first_distance < 0.01, f"Expected near-zero distance, got {first_distance}"

        # The last result should be the most distant
        last_distance = results[-1][1]
        assert last_distance > first_distance

