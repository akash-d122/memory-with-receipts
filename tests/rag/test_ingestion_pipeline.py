"""Tests for the ingestion pipeline (end-to-end with in-memory SQLite)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from memory_with_receipts.db.base import Base
from memory_with_receipts.ingestion.chunking.fixed_size import FixedSizeChunker
from memory_with_receipts.ingestion.chunking.structure_aware import StructureAwareChunker
from memory_with_receipts.ingestion.parsers.markdown_parser import MarkdownParser
from memory_with_receipts.ingestion.parsers.text_parser import TextParser
from memory_with_receipts.ingestion.pipeline import IngestionPipeline
from memory_with_receipts.rag.models import Chunk, Document


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database and session for testing."""
    # Import RAG models so they register with Base.metadata
    import memory_with_receipts.rag.models  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def pipeline() -> IngestionPipeline:
    """Create a pipeline with text + markdown parsers and fixed-size chunker."""
    return IngestionPipeline(
        parsers=[TextParser(), MarkdownParser()],
        chunker=FixedSizeChunker(chunk_size=100, chunk_overlap=10),
    )


@pytest.fixture
def structure_pipeline() -> IngestionPipeline:
    """Create a pipeline with structure-aware chunker."""
    return IngestionPipeline(
        parsers=[TextParser(), MarkdownParser()],
        chunker=StructureAwareChunker(chunk_size=100, chunk_overlap=10),
    )


class TestIngestionPipeline:
    """Tests for the full ingestion pipeline."""

    def test_ingest_text_creates_document_and_chunks(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        result = pipeline.ingest(
            session=db_session,
            raw_content="First paragraph.\n\nSecond paragraph.",
            source_type="text",
            title="Test Doc",
            uri="/path/to/test.txt",
        )

        assert not result.is_duplicate
        assert result.title == "Test Doc"
        assert result.source_type == "text"
        assert result.chunk_count > 0
        assert len(result.content_hash) == 64

        # Verify document persisted
        doc = db_session.query(Document).filter_by(id=result.document_id).first()
        assert doc is not None
        assert doc.title == "Test Doc"
        assert doc.source_type == "text"
        assert doc.uri == "/path/to/test.txt"

    def test_ingest_markdown_creates_document_and_chunks(
        self, db_session: Session, structure_pipeline: IngestionPipeline
    ) -> None:
        md = "# My Doc\n\nIntro content.\n\n## Section A\n\nSection A details."
        result = structure_pipeline.ingest(
            session=db_session,
            raw_content=md,
            source_type="markdown",
            title="MD Test",
        )

        assert not result.is_duplicate
        assert result.chunk_count > 0

        # Verify chunks have section metadata
        chunks = (
            db_session.query(Chunk)
            .filter_by(document_id=result.document_id)
            .order_by(Chunk.chunk_index)
            .all()
        )
        assert len(chunks) > 0
        # At least one chunk should have heading metadata
        section_titles = [c.section_title for c in chunks if c.section_title]
        assert len(section_titles) > 0

    def test_duplicate_content_deduped_by_hash(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        content = "Unique content for dedup testing."

        # First ingestion
        result1 = pipeline.ingest(
            session=db_session,
            raw_content=content,
            source_type="text",
            title="First",
        )
        assert not result1.is_duplicate

        # Second ingestion with same content
        result2 = pipeline.ingest(
            session=db_session,
            raw_content=content,
            source_type="text",
            title="Second",
        )
        assert result2.is_duplicate
        assert result2.document_id == result1.document_id
        assert result2.content_hash == result1.content_hash

        # Only one document in DB
        doc_count = db_session.query(Document).count()
        assert doc_count == 1

    def test_different_content_not_deduped(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        result1 = pipeline.ingest(
            session=db_session,
            raw_content="Content A.",
            source_type="text",
            title="Doc A",
        )
        result2 = pipeline.ingest(
            session=db_session,
            raw_content="Content B.",
            source_type="text",
            title="Doc B",
        )

        assert not result1.is_duplicate
        assert not result2.is_duplicate
        assert result1.document_id != result2.document_id

    def test_chunks_have_required_fields(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        result = pipeline.ingest(
            session=db_session,
            raw_content="A paragraph with some content.",
            source_type="text",
            title="Fields Test",
        )

        chunks = (
            db_session.query(Chunk)
            .filter_by(document_id=result.document_id)
            .all()
        )
        assert len(chunks) > 0

        for chunk in chunks:
            assert chunk.content
            assert len(chunk.content_hash) == 64
            assert chunk.chunk_index >= 0
            assert chunk.token_count > 0
            assert chunk.start_char >= 0
            assert chunk.end_char >= chunk.start_char

    def test_document_stores_content_hash_and_size(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        content = "Some content for size check."
        result = pipeline.ingest(
            session=db_session,
            raw_content=content,
            source_type="text",
            title="Size Test",
        )

        doc = db_session.query(Document).filter_by(id=result.document_id).first()
        assert doc is not None
        assert doc.content_hash == Document.compute_content_hash(content)
        assert doc.content_size_bytes == len(content.encode("utf-8"))
        assert doc.raw_content_text == content

    def test_document_metadata_stored(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        result = pipeline.ingest(
            session=db_session,
            raw_content="Content with metadata.",
            source_type="text",
            title="Meta Test",
            metadata={"author": "Test", "tags": ["a", "b"]},
        )

        doc = db_session.query(Document).filter_by(id=result.document_id).first()
        assert doc is not None
        assert doc.metadata_["author"] == "Test"
        assert doc.metadata_["tags"] == ["a", "b"]

    def test_unknown_source_type_raises_parsing_error(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        from memory_with_receipts.core.exceptions import ParsingError

        with pytest.raises(ParsingError, match="No parser registered"):
            pipeline.ingest(
                session=db_session,
                raw_content="Content.",
                source_type="unknown_format",
                title="Bad Type",
            )

    def test_no_embeddings_generated(
        self, db_session: Session, pipeline: IngestionPipeline
    ) -> None:
        """Pipeline without embedding_provider must not generate any embeddings."""
        from memory_with_receipts.rag.models import ChunkEmbedding

        result = pipeline.ingest(
            session=db_session,
            raw_content="Content for embedding check.",
            source_type="text",
            title="No Embed",
        )

        # Document and chunks should exist
        assert result.chunk_count > 0
        assert result.embeddings_created == 0

        # Verify no ChunkEmbedding rows were created
        embedding_count = db_session.query(ChunkEmbedding).count()
        assert embedding_count == 0


class TestIngestionPipelineWithEmbeddings:
    """Tests for the optional embedding step in the ingestion pipeline."""

    @pytest.fixture
    def embedding_pipeline(self) -> IngestionPipeline:
        """Create a pipeline with mock embedding provider."""
        from memory_with_receipts.embeddings.mock import MockEmbeddingProvider

        return IngestionPipeline(
            parsers=[TextParser(), MarkdownParser()],
            chunker=FixedSizeChunker(chunk_size=100, chunk_overlap=10),
            embedding_provider=MockEmbeddingProvider(dimension=384),
        )

    def test_ingest_with_embeddings_creates_chunk_embeddings(
        self, db_session: Session, embedding_pipeline: IngestionPipeline
    ) -> None:
        """Pipeline with embedding provider must create ChunkEmbedding rows."""
        from memory_with_receipts.rag.models import ChunkEmbedding

        result = embedding_pipeline.ingest(
            session=db_session,
            raw_content="Content that will be embedded during ingestion.",
            source_type="text",
            title="Embedded Doc",
        )

        assert not result.is_duplicate
        assert result.chunk_count > 0
        assert result.embeddings_created == result.chunk_count

        # Verify ChunkEmbedding rows exist
        embeddings = db_session.query(ChunkEmbedding).all()
        assert len(embeddings) == result.chunk_count

        # Verify embedding metadata
        for emb in embeddings:
            assert emb.embedding_model == "mock-embedding-model"
            assert emb.embedding_dimension == 384
            assert emb.embedding_provider == "mock"
            assert emb.embedded_at is not None
            # VectorCompat on SQLite stores as JSON, so verify we get a list back
            assert isinstance(emb.embedding, (list, str))

    def test_ingest_with_embeddings_correct_dimension(
        self, db_session: Session, embedding_pipeline: IngestionPipeline
    ) -> None:
        """Embedded vectors must have the correct dimension."""
        from memory_with_receipts.rag.models import ChunkEmbedding

        embedding_pipeline.ingest(
            session=db_session,
            raw_content="Dimension check content.",
            source_type="text",
            title="Dim Check",
        )

        emb = db_session.query(ChunkEmbedding).first()
        assert emb is not None
        vector = emb.embedding
        # On SQLite, VectorCompat stores as JSON string; parse if needed
        if isinstance(vector, str):
            import json

            vector = json.loads(vector)
        assert len(vector) == 384

    def test_duplicate_does_not_re_embed(
        self, db_session: Session, embedding_pipeline: IngestionPipeline
    ) -> None:
        """Duplicate ingestion must not create additional embeddings."""
        from memory_with_receipts.rag.models import ChunkEmbedding

        content = "Content for duplicate embedding test."

        # First ingestion
        result1 = embedding_pipeline.ingest(
            session=db_session,
            raw_content=content,
            source_type="text",
            title="First",
        )
        first_count = db_session.query(ChunkEmbedding).count()
        assert result1.embeddings_created > 0

        # Second ingestion with same content
        result2 = embedding_pipeline.ingest(
            session=db_session,
            raw_content=content,
            source_type="text",
            title="Second",
        )
        assert result2.is_duplicate
        assert result2.embeddings_created == 0

        # No additional embeddings created
        assert db_session.query(ChunkEmbedding).count() == first_count


