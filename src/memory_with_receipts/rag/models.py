"""RAG document, chunk, and chunk-embedding SQLAlchemy models.

These tables store ingested documents, their chunks, and vector embeddings.
The ChunkEmbedding model uses pgvector on Postgres and falls back to JSON
on SQLite for unit test portability.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator

from memory_with_receipts.core.config import Settings
from memory_with_receipts.db.base import Base
from memory_with_receipts.memory.models import GUID, JsonCompat, UTCDateTime


class VectorCompat(TypeDecorator):
    """pgvector Vector on Postgres, JSON list on SQLite.

    This lets unit tests run on in-memory SQLite while integration tests
    use real pgvector columns. The dimension is set at construction time.
    """

    impl = JSON  # fallback for SQLite
    cache_ok = True

    def __init__(self, dimension: int = 384) -> None:
        super().__init__()
        self._dimension = dimension

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self._dimension))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if dialect.name == "postgresql":
            # pgvector accepts lists directly
            return value
        # SQLite: store as JSON string
        return json.dumps(value) if isinstance(value, list) else value

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if dialect.name == "postgresql":
            # pgvector returns numpy array or list
            if hasattr(value, "tolist"):
                return value.tolist()
            return list(value)
        # SQLite: parse from JSON string
        if isinstance(value, str):
            return json.loads(value)
        return value


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
    embeddings: Mapped[list["ChunkEmbedding"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class ChunkEmbedding(Base):
    """Vector embedding for a text chunk.

    Stores the embedding vector alongside metadata about which model and
    provider generated it. The embedding column uses pgvector's Vector type
    on Postgres and falls back to JSON on SQLite for unit tests.
    """

    __tablename__ = "chunk_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("chunks.id"), nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(
        VectorCompat(Settings().embedding_dimension), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=lambda: datetime.now(UTC), nullable=False
    )

    chunk: Mapped[Chunk] = relationship(back_populates="embeddings")
