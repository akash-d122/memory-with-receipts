"""Shared FastAPI dependencies for RAG routes.

Lazy-initializes RAG database session factories, embedding providers,
retrieval search/generation services, and ingestion pipelines on first use.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from memory_with_receipts.embeddings.base import BaseEmbeddingProvider
    from memory_with_receipts.ingestion.pipeline import IngestionPipeline
    from memory_with_receipts.llm.generation import GenerationService
    from memory_with_receipts.rag.search_service import SearchService


def get_rag_session_factory(request: Request) -> sessionmaker:
    """Retrieve or lazy-initialize RAG database session factory."""
    if not getattr(request.app.state, "rag_session_factory", None):
        settings = request.app.state.settings
        db_url = settings.database_url
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        engine = create_engine(db_url, future=True)
        # Ensure pgvector extension exists on Postgres
        if "postgresql" in db_url:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
        request.app.state.rag_session_factory = sessionmaker(
            bind=engine, expire_on_commit=False, future=True
        )
    return request.app.state.rag_session_factory


def get_rag_db_session(request: Request) -> Generator[Session, None, None]:
    """Dependency: short-lived sync DB session for RAG queries.

    Yields one session per request and closes it automatically.
    Tests override this via ``app.dependency_overrides``.
    """
    session_factory = get_rag_session_factory(request)
    with session_factory() as session:
        yield session


def get_embedding_provider(request: Request) -> BaseEmbeddingProvider:
    """Retrieve or lazy-initialize the embedding provider."""
    if not getattr(request.app.state, "embedding_provider", None):
        settings = request.app.state.settings
        if settings.embedding_provider == "gemini":
            from memory_with_receipts.embeddings.gemini import GeminiEmbeddingProvider
            request.app.state.embedding_provider = GeminiEmbeddingProvider(
                api_key=settings.gemini_api_key,
                model_name=settings.embedding_model,
                dimension=settings.embedding_dimension,
            )
        elif settings.embedding_provider == "local":
            from memory_with_receipts.embeddings.local import LocalEmbeddingProvider
            request.app.state.embedding_provider = LocalEmbeddingProvider(
                model_name=settings.embedding_model,
                dimension=settings.embedding_dimension,
            )
        else:
            from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
            request.app.state.embedding_provider = MockEmbeddingProvider(
                dimension=settings.embedding_dimension
            )
    return request.app.state.embedding_provider


def get_search_service(request: Request) -> SearchService:
    """Retrieve or lazy-initialize SearchService."""
    if not getattr(request.app.state, "search_service", None):
        from memory_with_receipts.rag.search_service import SearchService
        provider = get_embedding_provider(request)
        request.app.state.search_service = SearchService(embedding_provider=provider)
    return request.app.state.search_service


def get_generation_service(request: Request) -> GenerationService:
    """Retrieve or lazy-initialize GenerationService."""
    if not getattr(request.app.state, "generation_service", None):
        from memory_with_receipts.llm.gemini import GeminiLLMProvider
        from memory_with_receipts.llm.generation import GenerationService
        from memory_with_receipts.llm.mock import MockLLMProvider

        settings = request.app.state.settings

        if settings.llm_provider == "gemini":
            llm_provider = GeminiLLMProvider(
                api_key=settings.gemini_api_key,
                model_name=settings.llm_model,
            )
        else:
            llm_provider = MockLLMProvider()

        search_service = get_search_service(request)
        request.app.state.generation_service = GenerationService(
            llm_provider=llm_provider,
            search_service=search_service,
            default_top_k=5,
        )
    return request.app.state.generation_service


def get_ingestion_pipeline(request: Request) -> IngestionPipeline:
    """Retrieve or lazy-initialize IngestionPipeline."""
    if not getattr(request.app.state, "ingestion_pipeline", None):
        from memory_with_receipts.ingestion.chunking.structure_aware import StructureAwareChunker
        from memory_with_receipts.ingestion.parsers.json_parser import JSONParser
        from memory_with_receipts.ingestion.parsers.markdown_parser import MarkdownParser
        from memory_with_receipts.ingestion.parsers.pdf_parser import PDFParser
        from memory_with_receipts.ingestion.parsers.text_parser import TextParser
        from memory_with_receipts.ingestion.parsers.web_parser import WebParser
        from memory_with_receipts.ingestion.pipeline import IngestionPipeline

        parsers = [
            MarkdownParser(),
            TextParser(),
            PDFParser(),
            WebParser(),
            JSONParser(),
        ]
        chunker = StructureAwareChunker()
        provider = get_embedding_provider(request)

        request.app.state.ingestion_pipeline = IngestionPipeline(
            parsers=parsers,
            chunker=chunker,
            embedding_provider=provider,
        )
    return request.app.state.ingestion_pipeline
