"""POST /v1/search — Document RAG hybrid retrieval endpoint."""

from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from memory_with_receipts.api.rag_dependencies import get_rag_db_session
from memory_with_receipts.api.search_schemas import SearchRequest, SearchResponse, SearchResult
from memory_with_receipts.core.exceptions import EmbeddingError, RetrievalError
from memory_with_receipts.core.logging import get_logger
from memory_with_receipts.rag.search_service import SearchService

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["search"])


def _get_search_service(request: Request) -> SearchService:
    """Dependency: retrieve SearchService from app state."""
    return request.app.state.search_service


@router.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest,
    request: Request,
    session: Annotated[Session, Depends(get_rag_db_session)],
    service: Annotated[SearchService, Depends(_get_search_service)],
) -> SearchResponse:
    """Hybrid search over ingested documents with receipt metadata."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    logger.info(
        "search_started",
        correlation_id=correlation_id,
        query=body.query[:100],
        top_k=body.top_k,
        enable_vector=body.enable_vector,
        enable_keyword=body.enable_keyword,
    )

    start = time.monotonic()

    try:
        results = service.search(
            session=session,
            query=body.query,
            top_k=body.top_k,
            source_type=body.source_type,
            date_from=body.date_from,
            date_to=body.date_to,
            metadata_filters=body.metadata_filters,
            enable_vector=body.enable_vector,
            enable_keyword=body.enable_keyword,
        )
    except EmbeddingError as e:
        logger.warning("search_embedding_error", correlation_id=correlation_id, error=str(e))
        raise RetrievalError(f"Embedding error: {e}") from e

    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

    search_results = [
        SearchResult(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_title=r.document_title,
            source_type=r.source_type,
            uri=r.uri,
            chunk_index=r.chunk_index,
            content=r.content,
            section_title=r.section_title,
            heading_path=r.heading_path,
            start_char=r.start_char,
            end_char=r.end_char,
            vector_score=r.vector_score,
            keyword_score=r.keyword_score,
            rrf_score=r.rrf_score,
            reason_codes=r.reason_codes,
            embedding_provider=r.embedding_provider,
            embedding_model=r.embedding_model,
        )
        for r in results
    ]

    logger.info(
        "search_completed",
        correlation_id=correlation_id,
        total_results=len(search_results),
        retrieval_time_ms=elapsed_ms,
    )

    return SearchResponse(
        correlation_id=correlation_id,
        query=body.query,
        total_results=len(search_results),
        retrieval_time_ms=elapsed_ms,
        results=search_results,
    )
