"""Schemas for document ingestion API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Payload for text/JSON document ingestion."""

    title: str = Field(..., description="Human-readable title of the document")
    content: str = Field(..., description="Document content text or markdown")
    source_type: str = Field(..., description="Type of source, e.g. 'text', 'markdown', 'json'")
    uri: str | None = Field(None, description="Optional source URI (e.g. file path, URL)")
    tags: str | None = Field(None, description="Comma-separated tags")
    metadata: dict[str, Any] | None = Field(None, description="Optional extra metadata dict")


class IngestResponse(BaseModel):
    """Response returned after successful ingestion."""

    correlation_id: str
    document_id: str
    title: str
    source_type: str
    chunk_count: int
    content_hash: str
    is_duplicate: bool
    embeddings_created: int = 0


class PrometheusAlert(BaseModel):
    """Individual alert payload from Prometheus Alertmanager."""

    status: str
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None
    generatorURL: str | None = None


class PrometheusWebhookPayload(BaseModel):
    """Payload for Prometheus Alertmanager webhook endpoint."""

    receiver: str | None = None
    status: str
    alerts: list[PrometheusAlert] = Field(default_factory=list)
    externalURL: str | None = None


class PrometheusWebhookResponse(BaseModel):
    """Response from Prometheus Alertmanager webhook ingestion."""

    correlation_id: str
    alerts_processed: int
    results: list[IngestResponse] = Field(default_factory=list)
