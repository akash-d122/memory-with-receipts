from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OperationalEventRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_type: str = Field(min_length=1, max_length=80)
    source_identifier: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    severity: str = Field(min_length=1, max_length=40)
    environment: str = Field(min_length=1, max_length=80)
    service_name: str = Field(min_length=1, max_length=120)
    host_name: str | None = Field(default=None, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    cluster: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    runbook_ref: str | None = None
    remediation_note: str | None = None
    occurred_at: datetime | None = None


class IngestionResponse(BaseModel):
    correlation_id: str
    source_record_id: str
    memory_record_id: str | None
    memory_key: str | None
    memory_created: bool
    idempotent_replay: bool
    evidence_count: int
    provenance_link_count: int


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    severity: str | None = None
    environment: str | None = None
    service_name: str | None = None
    host_name: str | None = None
    category: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    limit: int = Field(default=10, ge=1, le=50)


class FreshnessInfo(BaseModel):
    freshness_score: float
    first_seen_at: datetime
    last_seen_at: datetime


class ProvenanceReference(BaseModel):
    source_record_id: str
    source_identifier: str
    source_type: str
    title: str
    severity: str
    occurred_at: datetime
    evidence_record_id: str
    evidence_key: str
    evidence_value: Any
    link_reason: str


class RetrievedMemory(BaseModel):
    memory_id: str
    memory_key: str
    summary: str
    score: int
    reasons: list[str]
    freshness: FreshnessInfo
    provenance: list[ProvenanceReference]


class RetrievalResponse(BaseModel):
    correlation_id: str
    matched_memories: list[RetrievedMemory]
