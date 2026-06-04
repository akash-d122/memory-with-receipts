import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, JSON, TypeDecorator

from memory_with_receipts.db.base import Base


class GUID(TypeDecorator[uuid.UUID]):
    """PostgreSQL UUID in production, portable CHAR UUIDs in SQLite tests."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: uuid.UUID | str | None, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value: uuid.UUID | str | None, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetime stored consistently in PostgreSQL and SQLite tests."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


JsonCompat = JSONB().with_variant(JSON(), "sqlite")


class SourceType(StrEnum):
    NOTE = "note"
    DOCUMENT = "document"
    WEB = "web"
    CHAT = "chat"
    MANUAL = "manual"
    API = "api"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    CONTRADICTED = "contradicted"
    STALE = "stale"
    DISPUTED = "disputed"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    CHECKED = "checked"
    FAILED = "failed"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JsonCompat, default=dict, nullable=False
    )

    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="source")


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[MemoryStatus] = mapped_column(Enum(MemoryStatus), nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="memory")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memories.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), nullable=False, default=VerificationStatus.UNVERIFIED
    )

    memory: Mapped[Memory] = relationship(back_populates="evidence_items")
    source: Mapped[Source] = relationship(back_populates="evidence_items")
