"""POST /v1/ask — RAG answer generation with inline citations."""

from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from memory_with_receipts.api.ask_schemas import (
    AskRequest,
    AskResponse,
    CitationReceiptSchema,
)
from memory_with_receipts.api.rag_dependencies import get_rag_db_session
from memory_with_receipts.core.exceptions import GenerationError, RetrievalError
from memory_with_receipts.core.logging import get_logger
from memory_with_receipts.llm.generation import GenerationService

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["ask"])


def _get_generation_service(request: Request) -> GenerationService:
    """Dependency: retrieve GenerationService from app state."""
    return request.app.state.generation_service


@router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    request: Request,
    session: Annotated[Session, Depends(get_rag_db_session)],
    service: Annotated[GenerationService, Depends(_get_generation_service)],
) -> AskResponse:
    """Generate a grounded answer with inline citations and provenance receipts."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    settings = getattr(request.app.state, "settings", None)
    debug_mode = getattr(settings, "debug", False) if settings else False

    logger.info(
        "ask_started",
        correlation_id=correlation_id,
        query=body.query[:100],
        top_k=body.top_k,
    )

    start = time.monotonic()

    try:
        result = service.ask(
            session=session,
            query=body.query,
            top_k=body.top_k,
            source_type=body.source_type,
            metadata_filters=body.metadata_filters,
        )
    except (GenerationError, RetrievalError) as exc:
        logger.warning(
            "ask_error",
            correlation_id=correlation_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise

    total_ms = round((time.monotonic() - start) * 1000, 2)

    logger.info(
        "ask_completed",
        correlation_id=correlation_id,
        is_insufficient=result.is_insufficient,
        context_chunks_used=result.context_chunks_used,
        citations=len(result.citations),
        generation_time_ms=result.generation_time_ms,
        retrieval_time_ms=result.retrieval_time_ms,
        total_ms=total_ms,
    )

    citation_schemas = [
        CitationReceiptSchema(
            citation_index=c.citation_index,
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_title=c.document_title,
            source_type=c.source_type,
            uri=c.uri,
            chunk_index=c.chunk_index,
            section_title=c.section_title,
            heading_path=c.heading_path,
            start_char=c.start_char,
            end_char=c.end_char,
            content_snippet=c.content_snippet,
            vector_score=c.vector_score,
            keyword_score=c.keyword_score,
            rrf_score=c.rrf_score,
        )
        for c in result.citations
    ]

    return AskResponse(
        correlation_id=correlation_id,
        query=body.query,
        answer=result.answer,
        is_insufficient=result.is_insufficient,
        context_chunks_used=result.context_chunks_used,
        citations=citation_schemas,
        model=result.model,
        provider=result.provider,
        retrieval_time_ms=result.retrieval_time_ms,
        generation_time_ms=result.generation_time_ms,
        raw_prompt=result.raw_prompt if debug_mode else None,
    )
