"""Document ingestion pipeline.

Orchestrates: select parser → parse → select chunker → chunk → (embed) → persist.
Content-hash deduplication on documents.content_hash prevents re-ingestion
of identical content. When an embedding provider is configured, chunks are
embedded and stored as ChunkEmbedding rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from memory_with_receipts.core.exceptions import EmbeddingError, IngestionError, ParsingError
from memory_with_receipts.embeddings.base import BaseEmbeddingProvider
from memory_with_receipts.ingestion.chunking.base import BaseChunker
from memory_with_receipts.ingestion.parsers.base import BaseParser
from memory_with_receipts.rag.models import Chunk as ChunkModel
from memory_with_receipts.rag.models import ChunkEmbedding, Document


@dataclass
class IngestionResult:
    """Result of a successful document ingestion."""

    document_id: str
    title: str
    source_type: str
    chunk_count: int
    content_hash: str
    is_duplicate: bool
    embeddings_created: int = 0


class IngestionPipeline:
    """Orchestrates document ingestion: parse → chunk → (embed) → persist.

    Maintains a registry of parsers and selects the appropriate one
    based on source_type. Uses the configured chunker for splitting.
    When an embedding provider is set, chunks are automatically embedded
    during ingestion.
    """

    def __init__(
        self,
        parsers: list[BaseParser],
        chunker: BaseChunker,
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        self._parsers = parsers
        self._chunker = chunker
        self._embedding_provider = embedding_provider

    def _select_parser(self, source_type: str) -> BaseParser:
        """Find a parser that can handle the given source type."""
        for parser in self._parsers:
            if parser.can_parse(source_type):
                return parser
        raise ParsingError(
            f"No parser registered for source type: {source_type!r}. "
            f"Available parsers handle: {self._available_types()}"
        )

    def _available_types(self) -> str:
        """List source types handled by registered parsers (for error messages)."""
        types: list[str] = []
        for p in self._parsers:
            # Check common source types
            for t in ("text", "txt", "markdown", "md", "pdf", "web", "json"):
                if p.can_parse(t) and t not in types:
                    types.append(t)
        return ", ".join(types) or "none"

    def ingest(
        self,
        session: Session,
        raw_content: str | bytes,
        source_type: str,
        title: str,
        uri: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> IngestionResult:
        """Ingest a document: parse → chunk → (embed) → persist.

        Args:
            session: SQLAlchemy session for persistence.
            raw_content: Raw document content (text or bytes).
            source_type: Type of source (e.g. "text", "markdown").
            title: Human-readable document title.
            uri: Optional source URI (file path, URL, etc.).
            metadata: Optional additional metadata.

        Returns:
            IngestionResult with document ID, chunk count, and embeddings created.

        Raises:
            ParsingError: If no parser handles the source type.
            IngestionError: If persistence fails.
            EmbeddingError: If embedding generation fails.
        """
        metadata = metadata or {}

        # 1. Compute content hash for deduplication
        if isinstance(raw_content, bytes):
            content_text = raw_content.decode("utf-8", errors="replace")
        else:
            content_text = raw_content
        content_hash = Document.compute_content_hash(content_text)

        # 2. Check for duplicate
        existing = (
            session.query(Document)
            .filter(Document.content_hash == content_hash)
            .first()
        )
        if existing is not None:
            return IngestionResult(
                document_id=str(existing.id),
                title=existing.title,
                source_type=existing.source_type,
                chunk_count=len(existing.chunks),
                content_hash=content_hash,
                is_duplicate=True,
            )

        # 3. Parse
        parser = self._select_parser(source_type)
        parsed_doc = parser.parse(raw_content, metadata={**metadata, "title": title})

        # 4. Chunk
        chunks = self._chunker.chunk(parsed_doc)

        # 5. Persist document + chunks
        embeddings_created = 0
        try:
            document = Document(
                title=title,
                source_type=source_type,
                uri=uri,
                content_hash=content_hash,
                raw_content_text=content_text,
                content_size_bytes=len(content_text.encode("utf-8")),
                metadata_=metadata,
            )
            session.add(document)
            session.flush()  # Get the document ID

            # 6. Persist chunks
            chunk_models: list[ChunkModel] = []
            for chunk_data in chunks:
                chunk_model = ChunkModel(
                    document_id=document.id,
                    chunk_index=chunk_data.chunk_index,
                    content=chunk_data.content,
                    content_hash=chunk_data.content_hash,
                    section_title=chunk_data.section_title,
                    heading_path=chunk_data.heading_path,
                    page_number=chunk_data.page_number,
                    start_char=chunk_data.start_char,
                    end_char=chunk_data.end_char,
                    token_count=chunk_data.token_count,
                    metadata_=chunk_data.metadata,
                )
                session.add(chunk_model)
                chunk_models.append(chunk_model)

            session.flush()  # Get chunk IDs before embedding

            # 7. Optional: embed chunks if provider is configured
            if self._embedding_provider is not None and chunk_models:
                embeddings_created = self._embed_chunks(session, chunk_models)

            session.commit()
        except (EmbeddingError, IngestionError):
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise IngestionError(f"Failed to persist document: {e}") from e

        return IngestionResult(
            document_id=str(document.id),
            title=title,
            source_type=source_type,
            chunk_count=len(chunks),
            content_hash=content_hash,
            is_duplicate=False,
            embeddings_created=embeddings_created,
        )

    def _embed_chunks(self, session: Session, chunk_models: list[ChunkModel]) -> int:
        """Embed chunk contents and persist ChunkEmbedding rows.

        Args:
            session: SQLAlchemy session.
            chunk_models: Persisted chunk models with IDs.

        Returns:
            Number of embeddings created.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        provider = self._embedding_provider
        assert provider is not None  # Caller checks, but satisfy type checker

        texts = [cm.content for cm in chunk_models]
        vectors = provider.embed(texts)

        for chunk_model, vector in zip(chunk_models, vectors, strict=True):
            provider.validate_dimension(vector)
            embedding = ChunkEmbedding(
                chunk_id=chunk_model.id,
                embedding=vector,
                embedding_model=provider.model_name,
                embedding_dimension=provider.dimension,
                embedding_provider=provider.provider_name,
                embedded_at=datetime.now(UTC),
            )
            session.add(embedding)

        return len(vectors)

