from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from memory_with_receipts.api.dependencies import get_operational_db_session
from memory_with_receipts.api.schemas import (
    IngestionResponse,
    OperationalEventRequest,
    RetrievalRequest,
    RetrievalResponse,
)
from memory_with_receipts.core.logging import get_logger
from memory_with_receipts.memory.ingestion import ingest_operational_event
from memory_with_receipts.retrieval.scoring import score_operational_memories

router = APIRouter(prefix="/operational-memory", tags=["operational-memory"])
logger = get_logger(__name__)


@router.post(
    "/events",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_event(
    payload: OperationalEventRequest,
    request: Request,
    session: Annotated[Session, Depends(get_operational_db_session)],
) -> IngestionResponse:
    correlation_id = request.state.correlation_id
    payload_data = payload.model_dump(mode="json", exclude_none=True)
    logger.info(
        "operational_ingestion_request_received",
        correlation_id=correlation_id,
        source_identifier=payload.source_identifier,
        category=payload.category,
        service_name=payload.service_name,
        host_name=payload.host_name,
    )
    try:
        result = ingest_operational_event(session, payload_data, correlation_id=correlation_id)
    except ValueError as exc:
        logger.warning(
            "operational_ingestion_validation_failed",
            correlation_id=correlation_id,
            source_identifier=payload.source_identifier,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_operational_event", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception(
            "operational_ingestion_failed",
            correlation_id=correlation_id,
            source_identifier=payload.source_identifier,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ingestion_failed", "message": "Operational event ingestion failed"},
        ) from exc

    status_code = "idempotent_replay" if result["idempotent_replay"] else "created_or_updated"
    logger.info(
        "operational_ingestion_request_finished",
        correlation_id=correlation_id,
        source_record_id=result["source_record_id"],
        memory_record_id=result["memory_record_id"],
        result=status_code,
    )
    return IngestionResponse(correlation_id=correlation_id, **result)


@router.post("/retrieval", response_model=RetrievalResponse)
def retrieve_memories(
    payload: RetrievalRequest,
    request: Request,
    session: Annotated[Session, Depends(get_operational_db_session)],
) -> RetrievalResponse:
    correlation_id = request.state.correlation_id
    payload_data = payload.model_dump(mode="json", exclude_none=True)
    limit = payload_data.pop("limit")
    logger.info(
        "operational_retrieval_request_received",
        correlation_id=correlation_id,
        service_name=payload.service_name,
        host_name=payload.host_name,
        category=payload.category,
        limit=limit,
    )
    try:
        results = score_operational_memories(
            session,
            payload_data,
            limit=limit,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.exception(
            "operational_retrieval_failed",
            correlation_id=correlation_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "retrieval_failed", "message": "Operational memory retrieval failed"},
        ) from exc

    logger.info(
        "operational_retrieval_request_finished",
        correlation_id=correlation_id,
        result_count=len(results),
    )
    return RetrievalResponse(correlation_id=correlation_id, matched_memories=results)
