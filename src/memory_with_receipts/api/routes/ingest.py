"""POST /v1/ingest — Document and file ingestion endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from memory_with_receipts.api.ingest_schemas import (
    IngestRequest,
    IngestResponse,
    PrometheusAlert,
    PrometheusWebhookPayload,
    PrometheusWebhookResponse,
)
from memory_with_receipts.api.rag_dependencies import get_ingestion_pipeline, get_rag_db_session
from memory_with_receipts.core.exceptions import IngestionError, ParsingError
from memory_with_receipts.core.logging import get_logger
from memory_with_receipts.ingestion.pipeline import IngestionPipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["ingest"])


def detect_source_type_from_filename(filename: str) -> str:
    """Detect source_type from filename extension."""
    if not filename:
        return "text"
    parts = filename.split(".")
    if len(parts) < 2:
        return "text"
    ext = parts[-1].lower()
    if ext in ("md", "markdown"):
        return "markdown"
    elif ext == "pdf":
        return "pdf"
    elif ext == "json":
        return "json"
    elif ext in ("html", "htm"):
        return "web"
    return "text"


def format_prometheus_alert_to_markdown(alert: PrometheusAlert) -> str:
    """Format a Prometheus Alertmanager alert into standard Markdown."""
    alertname = alert.labels.get("alertname", "UnknownAlert")
    severity = alert.labels.get("severity", "warning")
    instance = alert.labels.get("instance", "unknown-instance")
    database = alert.labels.get("database", alert.labels.get("db", "unknown-db"))
    timestamp = alert.startsAt or "unknown-time"
    status = alert.status
    summary = alert.annotations.get(
        "summary", alert.annotations.get("message", "No summary provided.")
    )
    description = alert.annotations.get("description", "No description provided.")

    # Format labels/annotations lists
    labels_list = "\n".join(
        f"- **{k}**: {v}"
        for k, v in alert.labels.items()
        if k not in ("alertname", "severity", "instance", "database", "db")
    )
    annotations_list = "\n".join(
        f"- **{k}**: {v}"
        for k, v in alert.annotations.items()
        if k not in ("summary", "description")
    )

    markdown = f"""# Prometheus Alert: {alertname}

## Alert Information
- **Alert Name**: {alertname}
- **Severity**: {severity}
- **Instance**: {instance}
- **Database**: {database}
- **Timestamp**: {timestamp}
- **Status**: {status}
- **Source**: Prometheus Alertmanager

## Alert Summary
{summary}

## Alert Description
{description}
"""
    if labels_list:
        markdown += f"\n## Extra Labels\n{labels_list}\n"
    if annotations_list:
        markdown += f"\n## Extra Annotations\n{annotations_list}\n"
    if alert.generatorURL:
        markdown += f"\n## Source Links\n- **Generator URL**: {alert.generatorURL}\n"

    return markdown


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(
    body: IngestRequest,
    request: Request,
    session: Annotated[Session, Depends(get_rag_db_session)],
    pipeline: Annotated[IngestionPipeline, Depends(get_ingestion_pipeline)],
) -> IngestResponse:
    """Ingest a document from a raw JSON body."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.info(
        "ingest_json_started",
        correlation_id=correlation_id,
        title=body.title,
        source_type=body.source_type,
    )

    metadata = body.metadata or {}
    if body.tags:
        metadata["tags"] = body.tags

    try:
        res = pipeline.ingest(
            session=session,
            raw_content=body.content,
            source_type=body.source_type,
            title=body.title,
            uri=body.uri,
            metadata=metadata,
        )
    except (IngestionError, ParsingError) as e:
        logger.error(
            "ingest_json_failed",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception(
            "ingest_json_unexpected_error",
            correlation_id=correlation_id,
        )
        raise HTTPException(status_code=500, detail=f"Unexpected ingestion failure: {e}") from e

    logger.info(
        "ingest_json_completed",
        correlation_id=correlation_id,
        document_id=res.document_id,
        chunk_count=res.chunk_count,
        is_duplicate=res.is_duplicate,
    )

    return IngestResponse(
        correlation_id=correlation_id,
        document_id=res.document_id,
        title=res.title,
        source_type=res.source_type,
        chunk_count=res.chunk_count,
        content_hash=res.content_hash,
        is_duplicate=res.is_duplicate,
        embeddings_created=res.embeddings_created,
    )


@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    request: Request,
    session: Annotated[Session, Depends(get_rag_db_session)],
    pipeline: Annotated[IngestionPipeline, Depends(get_ingestion_pipeline)],
    file: Annotated[UploadFile, File(...)],
    title: Annotated[str | None, Form()] = None,
    source_type: Annotated[str | None, Form()] = None,
    uri: Annotated[str | None, Form()] = None,
    tags: Annotated[str | None, Form()] = None,
) -> IngestResponse:
    """Ingest a document uploaded as a file."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    doc_title = title or file.filename or "uploaded_file"
    doc_source_type = source_type or detect_source_type_from_filename(file.filename or "")

    logger.info(
        "ingest_file_started",
        correlation_id=correlation_id,
        filename=file.filename,
        title=doc_title,
        source_type=doc_source_type,
    )

    try:
        content_bytes = await file.read()
    except Exception as e:
        logger.error(
            "ingest_file_read_failed",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=f"Failed to read file payload: {e}") from e

    metadata = {}
    if tags:
        metadata["tags"] = tags

    try:
        res = pipeline.ingest(
            session=session,
            raw_content=content_bytes,
            source_type=doc_source_type,
            title=doc_title,
            uri=uri or file.filename,
            metadata=metadata,
        )
    except (IngestionError, ParsingError) as e:
        logger.error(
            "ingest_file_failed",
            correlation_id=correlation_id,
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception(
            "ingest_file_unexpected_error",
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Unexpected file ingestion failure: {e}"
        ) from e

    logger.info(
        "ingest_file_completed",
        correlation_id=correlation_id,
        document_id=res.document_id,
        chunk_count=res.chunk_count,
        is_duplicate=res.is_duplicate,
    )

    return IngestResponse(
        correlation_id=correlation_id,
        document_id=res.document_id,
        title=res.title,
        source_type=res.source_type,
        chunk_count=res.chunk_count,
        content_hash=res.content_hash,
        is_duplicate=res.is_duplicate,
        embeddings_created=res.embeddings_created,
    )


@router.post("/ingest/webhook/prometheus", response_model=PrometheusWebhookResponse)
def ingest_prometheus_webhook(
    payload: PrometheusWebhookPayload,
    request: Request,
    session: Annotated[Session, Depends(get_rag_db_session)],
    pipeline: Annotated[IngestionPipeline, Depends(get_ingestion_pipeline)],
) -> PrometheusWebhookResponse:
    """Ingest alerts received from a Prometheus Alertmanager webhook configuration."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.info(
        "ingest_prometheus_webhook_started",
        correlation_id=correlation_id,
        receiver=payload.receiver,
        alert_count=len(payload.alerts),
    )

    results: list[IngestResponse] = []

    for alert in payload.alerts:
        alertname = alert.labels.get("alertname", "UnknownAlert")
        severity = alert.labels.get("severity", "warning")
        instance = alert.labels.get("instance", "unknown")

        title = f"Prometheus Alert: {alertname}"
        markdown_content = format_prometheus_alert_to_markdown(alert)
        uri = f"prometheus://alertmanager/{alertname}/{instance}"

        # Combine labels & annotations into metadata for advanced filtering
        metadata = {
            "source": "prometheus-webhook",
            "type": "prometheus-alert",
            "status": alert.status,
            "severity": severity,
            "instance": instance,
            "alertname": alertname,
            "tags": f"prometheus,alert,live,{severity}",
            "starts_at": alert.startsAt,
            **alert.labels,
            **alert.annotations,
        }

        try:
            res = pipeline.ingest(
                session=session,
                raw_content=markdown_content,
                source_type="markdown",
                title=title,
                uri=uri,
                metadata=metadata,
            )
            results.append(
                IngestResponse(
                    correlation_id=correlation_id,
                    document_id=res.document_id,
                    title=res.title,
                    source_type=res.source_type,
                    chunk_count=res.chunk_count,
                    content_hash=res.content_hash,
                    is_duplicate=res.is_duplicate,
                    embeddings_created=res.embeddings_created,
                )
            )
        except Exception as e:
            logger.error(
                "ingest_prometheus_alert_failed",
                correlation_id=correlation_id,
                alertname=alertname,
                instance=instance,
                error=str(e),
            )
            # We log the error but keep processing other alerts in the payload

    logger.info(
        "ingest_prometheus_webhook_completed",
        correlation_id=correlation_id,
        alerts_processed=len(results),
    )

    return PrometheusWebhookResponse(
        correlation_id=correlation_id,
        alerts_processed=len(results),
        results=results,
    )
