"""Document ingestion pipeline.

Orchestrates: select parser → parse → select chunker → chunk → persist.
Content-hash deduplication on documents.content_hash prevents re-ingestion
of identical content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from memory_with_receipts.core.exceptions import IngestionError, ParsingError
from memory_with_receipts.ingestion.chunking.base import BaseChunker
from memory_with_receipts.ingestion.parsers.base import BaseParser
from memory_with_receipts.rag.models import Chunk as ChunkModel
from memory_with_receipts.rag.models import Document


@dataclass
class IngestionResult:
    """Result of a successful document ingestion."""

    document_id: str
    title: str
    source_type: str
    chunk_count: int
    content_hash: str
    is_duplicate: bool


class IngestionPipeline:
    """Orchestrates document ingestion: parse → chunk → persist.

    Maintains a registry of parsers and selects the appropriate one
    based on source_type. Uses the configured chunker for splitting.
    """

    def __init__(
        self,
        parsers: list[BaseParser],
        chunker: BaseChunker,
    ) -> None:
        self._parsers = parsers
        self._chunker = chunker

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
        """Ingest a document: parse → chunk → persist.

        Args:
            session: SQLAlchemy session for persistence.
            raw_content: Raw document content (text or bytes).
            source_type: Type of source (e.g. "text", "markdown").
            title: Human-readable document title.
            uri: Optional source URI (file path, URL, etc.).
            metadata: Optional additional metadata.

        Returns:
            IngestionResult with document ID and chunk count.

        Raises:
            ParsingError: If no parser handles the source type.
            IngestionError: If persistence fails.
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

        # 5. Persist document
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

            session.commit()
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
        )
