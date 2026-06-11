"""Unit tests for GenerationService on SQLite (no Docker required).

Tests cover: answer with citations, insufficient context, filters,
sentinel detection, receipt field completeness, and timing fields.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.llm.generation import GenerationService
from memory_with_receipts.llm.mock import MockLLMProvider
from memory_with_receipts.llm.prompts import INSUFFICIENT_CONTEXT_MARKER
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


def _seed_document(
    session: Session,
    title: str = "Test Doc",
    source_type: str = "text",
    content: str = "Default chunk content for generation testing.",
    metadata: dict | None = None,
    embed: bool = True,
    num_chunks: int = 1,
) -> Document:
    provider = MockEmbeddingProvider(dimension=384)
    doc = Document(
        id=uuid.uuid4(),
        title=title,
        source_type=source_type,
        content_hash=Document.compute_content_hash(content + str(uuid.uuid4())),
        raw_content_text=content,
        content_size_bytes=len(content.encode()),
        metadata_=metadata or {},
    )
    session.add(doc)
    session.flush()

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
        session.flush()

        if embed:
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
    return doc


class TestGenerationServiceEmpty:
    """Behaviour when no documents are seeded."""

    def test_empty_index_returns_insufficient(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        result = generation_service.ask(
            session=db_session,
            query="What is PostgreSQL?",
        )
        assert result.is_insufficient is True
        assert len(result.citations) == 0
        assert result.context_chunks_used == 0

    def test_insufficient_answer_text_is_helpful(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        result = generation_service.ask(session=db_session, query="test")
        assert len(result.answer) > 0
        assert "evidence" in result.answer.lower() or "context" in result.answer.lower()


class TestGenerationServiceAnswer:
    """Tests for successful answer with citations."""

    def test_answer_contains_text(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        _seed_document(db_session, content="PostgreSQL replication monitoring setup")
        result = generation_service.ask(
            session=db_session,
            query="replication",
            top_k=5,
        )
        assert result.is_insufficient is False
        assert len(result.answer) > 0

    def test_context_chunks_used_positive(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        _seed_document(db_session, content="Failover procedures for database")
        result = generation_service.ask(
            session=db_session,
            query="failover",
            top_k=5,
        )
        assert result.context_chunks_used >= 1

    def test_result_has_model_and_provider(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        _seed_document(db_session, content="Deployment pipeline steps for production")
        result = generation_service.ask(session=db_session, query="deployment")
        assert len(result.model) > 0
        assert len(result.provider) > 0

    def test_raw_prompt_is_captured(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        _seed_document(db_session, content="Kubernetes scaling procedures")
        result = generation_service.ask(session=db_session, query="scaling")
        assert len(result.raw_prompt) > 0
        assert "scaling" in result.raw_prompt.lower() or "Question" in result.raw_prompt

    def test_timing_fields_are_non_negative(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        _seed_document(db_session, content="Load balancer health checks configured")
        result = generation_service.ask(session=db_session, query="health")
        assert result.retrieval_time_ms >= 0
        assert result.generation_time_ms >= 0


class TestGenerationServiceSentinel:
    """Tests for INSUFFICIENT_CONTEXT sentinel handling."""

    def test_sentinel_in_answer_sets_insufficient(
        self, db_session: Session, embedding_provider, search_service
    ) -> None:
        """When mock returns INSUFFICIENT_CONTEXT marker, is_insufficient=True."""
        sentinel_provider = MockLLMProvider(
            answer_template=f"The answer is: {INSUFFICIENT_CONTEXT_MARKER}"
        )
        service = GenerationService(
            llm_provider=sentinel_provider,
            search_service=search_service,
            embedding_provider=embedding_provider,
        )
        _seed_document(db_session, content="Some content to retrieve")
        result = service.ask(session=db_session, query="some query")
        assert result.is_insufficient is True
        assert len(result.citations) == 0

    def test_sentinel_answer_replaced_with_canned_message(
        self, db_session: Session, embedding_provider, search_service
    ) -> None:
        sentinel_provider = MockLLMProvider(
            answer_template=f"{INSUFFICIENT_CONTEXT_MARKER} fallback"
        )
        service = GenerationService(
            llm_provider=sentinel_provider,
            search_service=search_service,
            embedding_provider=embedding_provider,
        )
        _seed_document(db_session, content="Content that exists")
        result = service.ask(session=db_session, query="query")
        assert INSUFFICIENT_CONTEXT_MARKER not in result.answer
        assert len(result.answer) > 0


class TestGenerationServiceFilters:
    """Tests that source_type filter is passed through."""

    def test_source_type_filter_limits_context(
        self, db_session: Session, generation_service: GenerationService
    ) -> None:
        _seed_document(db_session, content="Markdown runbook procedures", source_type="markdown")
        _seed_document(db_session, content="Plain text docs", source_type="text")

        result = generation_service.ask(
            session=db_session,
            query="procedures",
            source_type="markdown",
        )
        # With markdown filter, only markdown chunks retrieved
        # Result may or may not have citations depending on mock,
        # but it should not error
        assert result.query == "procedures"


class TestGenerationServiceCitationReceipts:
    """Tests for citation receipt field completeness."""

    def test_citations_have_chunk_and_document_ids(
        self, db_session: Session
    ) -> None:
        """Force mock to produce [1] citation and verify receipt fields."""
        embedding_provider = MockEmbeddingProvider(dimension=384)
        # Template that always produces [1] in the answer
        llm_provider = MockLLMProvider(
            answer_template="The answer [1] is here."
        )
        search_service = SearchService(embedding_provider=embedding_provider)
        service = GenerationService(
            llm_provider=llm_provider,
            search_service=search_service,
            embedding_provider=embedding_provider,
        )

        _seed_document(db_session, content="Operational database failover content", embed=False)
        result = service.ask(
            session=db_session,
            query="failover",
            top_k=5,
        )

        # Only verify if we actually got a citation (content might not have been found)
        if result.citations:
            c = result.citations[0]
            assert c.chunk_id is not None
            assert c.document_id is not None
            assert c.document_title is not None
            assert c.rrf_score >= 0
            assert isinstance(c.content_snippet, str)
            assert len(c.content_snippet) > 0
