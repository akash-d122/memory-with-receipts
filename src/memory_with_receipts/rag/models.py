"""RAG document and chunk SQLAlchemy models.

These tables store ingested documents and their chunks. No embedding
columns here — those are added in Phase 3 via a separate migration.
"""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memory_with_receipts.db.base import Base
from memory_with_receipts.memory.models import GUID, JsonCompat, UTCDateTime


class Document(Base):
    """A top-level ingested document/source.

    Each document has a content_hash (SHA-256 of raw_content_text) used for
    deduplication. Re-ingesting identical content is a no-op.
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_documents_content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonCompat, default=dict, nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(UTC), nullable=False
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """SHA-256 hash of content for deduplication."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Chunk(Base):
    """An individual text chunk derived from a Document.

    Stores the chunk text, positional metadata (offsets, page, heading path),
    and a content hash for integrity checks.
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonCompat, default=dict, nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
