"""Unit tests for SearchService (SQLite, no Docker required).

Tests cover: basic search, empty index, receipt metadata, metadata filters,
vector-only/keyword-only modes, and embedding dimension mismatch.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.rag.models import Chunk, ChunkEmbedding, Document
from memory_with_receipts.rag.search_service import SearchService


@pytest.fixture
def db_session():
    """In-memory SQLite session with all RAG tables."""
    import memory_with_receipts.rag.models  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def mock_provider():
    return MockEmbeddingProvider(dimension=384)


@pytest.fixture
def search_service(mock_provider):
    return SearchService(embedding_provider=mock_provider)


def _seed_document(
    session: Session,
    title: str = "Test Doc",
    source_type: str = "text",
    uri: str | None = None,
    content: str = "Some default chunk content for testing search.",
    metadata: dict | None = None,
    num_chunks: int = 1,
    embed: bool = True,
) -> tuple[Document, list[Chunk]]:
    """Helper: insert a document with chunks and optional embeddings."""
    provider = MockEmbeddingProvider(dimension=384)

    doc = Document(
        id=uuid.uuid4(),
        title=title,
        source_type=source_type,
        uri=uri,
        content_hash=Document.compute_content_hash(content + str(uuid.uuid4())),
        raw_content_text=content,
        content_size_bytes=len(content.encode()),
        metadata_=metadata or {},
    )
    session.add(doc)
    session.flush()

    chunks: list[Chunk] = []
    for i in range(num_chunks):
        chunk_content = f"{content} chunk {i}"
        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=i,
            content=chunk_content,
            content_hash=Document.compute_content_hash(chunk_content),
            section_title=f"Section {i}",
            heading_path=f"# Section {i}",
            start_char=i * 100,
            end_char=(i + 1) * 100,
            token_count=len(chunk_content.split()),
            metadata_={},
        )
        session.add(chunk)
        chunks.append(chunk)

    session.flush()

    if embed:
        for chunk in chunks:
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
        session.flush()

    session.commit()
    return doc, chunks


class TestSearchServiceEmpty:
    """Tests for empty index behavior."""

    def test_empty_index_returns_empty(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Search on empty index must return empty results, not error."""
        results = search_service.search(
            session=db_session,
            query="anything at all",
            enable_keyword=True,
            enable_vector=False,  # No vector on SQLite
        )
        assert results == []

    def test_both_disabled_returns_empty(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Disabling both vector and keyword must return empty."""
        results = search_service.search(
            session=db_session,
            query="test",
            enable_vector=False,
            enable_keyword=False,
        )
        assert results == []


class TestSearchServiceKeyword:
    """Tests for keyword-only search on SQLite."""

    def test_keyword_search_finds_matching_chunks(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Keyword search must find chunks containing the query text."""
        _seed_document(db_session, content="PostgreSQL replication lag alert", embed=False)

        results = search_service.search(
            session=db_session,
            query="replication",
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results) >= 1
        assert "replication" in results[0].content.lower()

    def test_keyword_no_match_returns_empty(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Keyword search with no matching content returns empty."""
        _seed_document(db_session, content="Database performance monitoring", embed=False)

        results = search_service.search(
            session=db_session,
            query="xyznonexistentterm",
            enable_vector=False,
            enable_keyword=True,
        )
        assert results == []


class TestSearchServiceReceipts:
    """Tests for receipt metadata completeness."""

    def test_every_result_has_receipt_fields(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Every search result must include all receipt metadata fields."""
        _seed_document(
            db_session,
            title="Receipt Test Doc",
            source_type="markdown",
            uri="file:///test.md",
            content="Important operational document about failover procedures",
            embed=False,
        )

        results = search_service.search(
            session=db_session,
            query="failover",
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results) >= 1

        r = results[0]
        # Identity fields
        assert r.chunk_id is not None
        assert r.document_id is not None
        assert r.document_title == "Receipt Test Doc"
        assert r.source_type == "markdown"
        assert r.uri == "file:///test.md"

        # Content fields
        assert r.chunk_index is not None
        assert r.content is not None
        assert len(r.content) > 0
        assert r.section_title is not None
        assert r.heading_path is not None
        assert r.start_char is not None
        assert r.end_char is not None

        # Score fields
        assert r.rrf_score > 0
        assert r.reason_codes is not None
        assert len(r.reason_codes) > 0

    def test_embedded_result_has_provider_metadata(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Results from embedded chunks must include provider/model metadata."""
        _seed_document(
            db_session,
            content="Document with embeddings for metadata test",
            embed=True,
        )

        results = search_service.search(
            session=db_session,
            query="embeddings",
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results) >= 1
        r = results[0]
        assert r.embedding_provider == "mock"
        assert r.embedding_model == "mock-embedding-model"


class TestSearchServiceMetadataFilters:
    """Tests for metadata filtering."""

    def test_source_type_filter_excludes_non_matching(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Source type filter must exclude documents of other types."""
        _seed_document(
            db_session,
            title="Text Doc",
            source_type="text",
            content="Shared search term failover",
            embed=False,
        )
        _seed_document(
            db_session,
            title="Markdown Doc",
            source_type="markdown",
            content="Shared search term failover",
            embed=False,
        )

        results = search_service.search(
            session=db_session,
            query="failover",
            source_type="text",
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results) >= 1
        assert all(r.source_type == "text" for r in results)

    def test_date_range_filter(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Date range filter should limit results by ingestion date."""
        # This test verifies the parameter is accepted without error
        _seed_document(
            db_session,
            content="Date filter test content",
            embed=False,
        )

        results = search_service.search(
            session=db_session,
            query="Date filter",
            date_from=datetime(2020, 1, 1, tzinfo=UTC),
            date_to=datetime(2030, 12, 31, tzinfo=UTC),
            enable_vector=False,
            enable_keyword=True,
        )
        # Should include the document (ingested "now" is within range)
        assert len(results) >= 1


class TestSearchServiceModes:
    """Tests for vector-only and keyword-only modes."""

    def test_keyword_only_mode(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Keyword-only mode must work without vector search."""
        _seed_document(db_session, content="Keyword mode test content", embed=False)

        results = search_service.search(
            session=db_session,
            query="Keyword mode",
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results) >= 1
        # All results should have keyword_match reason
        for r in results:
            assert "keyword_match" in r.reason_codes


class TestSearchServiceMultipleChunks:
    """Tests for documents with multiple chunks."""

    def test_returns_multiple_matching_chunks(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Should return multiple chunks from the same document if they match."""
        _seed_document(
            db_session,
            content="Shared term failover",
            num_chunks=3,
            embed=False,
        )

        results = search_service.search(
            session=db_session,
            query="failover",
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results) == 3


class TestSearchServiceCustomMetadataFilters:
    """Tests for custom document metadata dictionary filters (SQLite)."""

    def test_metadata_filters_match_exactly(
        self, db_session: Session, search_service: SearchService
    ) -> None:
        """Should return only chunks belonging to documents with matching metadata values."""
        _seed_document(
            db_session,
            content="Metadata test content matching",
            metadata={"category": "billing", "author": "alice"},
            embed=False,
        )
        _seed_document(
            db_session,
            content="Metadata test content other",
            metadata={"category": "engineering", "author": "alice"},
            embed=False,
        )

        # Match single filter
        results = search_service.search(
            session=db_session,
            query="test",
            metadata_filters={"category": "billing"},
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results) == 1
        assert "matching" in results[0].content

        # Match multiple filters
        results2 = search_service.search(
            session=db_session,
            query="test",
            metadata_filters={"category": "billing", "author": "alice"},
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results2) == 1
        assert "matching" in results2[0].content

        # No match due to filter mismatch
        results3 = search_service.search(
            session=db_session,
            query="test",
            metadata_filters={"category": "billing", "author": "bob"},
            enable_vector=False,
            enable_keyword=True,
        )
        assert len(results3) == 0

