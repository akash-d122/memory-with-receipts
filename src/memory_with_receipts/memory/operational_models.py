from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memory_with_receipts.db.base import Base
from memory_with_receipts.memory.models import GUID, JsonCompat, UTCDateTime


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourceRecord(Base):
    """Immutable raw operational event source.

    Examples: database alarms, replication lag alerts, failover events, CPU/storage alerts,
    maintenance notices, deadlock spikes, and connection exhaustion incidents.
    """

    __tablename__ = "source_records"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_identifier: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    host_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JsonCompat, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    evidence_records: Mapped[list[EvidenceRecord]] = relationship(
        back_populates="source_record", cascade="all, delete-orphan"
    )
    provenance_links: Mapped[list[ProvenanceLink]] = relationship(back_populates="source_record")

    __table_args__ = (
        Index(
            "ix_source_records_operational_lookup",
            "environment",
            "service_name",
            "host_name",
            "severity",
        ),
    )


class EvidenceRecord(Base):
    """Structured deterministic evidence extracted from an operational source record."""

    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_records.id"), nullable=False, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    evidence_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    evidence_value: Mapped[Any] = mapped_column(JsonCompat, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    extracted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    source_record: Mapped[SourceRecord] = relationship(back_populates="evidence_records")
    provenance_links: Mapped[list[ProvenanceLink]] = relationship(back_populates="evidence_record")


class MemoryRecord(Base):
    """Higher-level operational memory abstraction backed by provenance receipts."""

    __tablename__ = "memory_records"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    memory_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", index=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    contradiction_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)

    provenance_links: Mapped[list[ProvenanceLink]] = relationship(
        back_populates="memory_record", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_memory_records_type_status_recent", "memory_type", "status", "last_seen_at"),
    )


class ProvenanceLink(Base):
    """Receipt linking a memory to the source and evidence that support it."""

    __tablename__ = "provenance_links"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    memory_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memory_records.id"), nullable=False, index=True
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_records.id"), nullable=False, index=True
    )
    evidence_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_records.id"), nullable=False, index=True
    )
    link_reason: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    memory_record: Mapped[MemoryRecord] = relationship(back_populates="provenance_links")
    source_record: Mapped[SourceRecord] = relationship(back_populates="provenance_links")
    evidence_record: Mapped[EvidenceRecord] = relationship(back_populates="provenance_links")
