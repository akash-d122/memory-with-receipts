"""Abstract base classes and data types for chunking strategies."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from memory_with_receipts.ingestion.parsers.base import ParsedDocument


@dataclass
class Chunk:
    """An individual text chunk ready for storage.

    Contains the chunk text plus positional and structural metadata needed
    for receipt construction downstream.
    """

    content: str
    chunk_index: int
    content_hash: str = ""
    section_title: str | None = None
    heading_path: str | None = None
    page_number: int | None = None
    start_char: int = 0
    end_char: int = 0
    token_count: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class BaseChunker(ABC):
    """Abstract interface for document chunking strategies."""

    @abstractmethod
    def chunk(self, parsed_doc: ParsedDocument) -> list[Chunk]:
        """Split a parsed document into chunks.

        Args:
            parsed_doc: The structured output from a parser.

        Returns:
            Ordered list of Chunks with positional metadata.

        Raises:
            ChunkingError: If chunking fails.
        """
        ...
