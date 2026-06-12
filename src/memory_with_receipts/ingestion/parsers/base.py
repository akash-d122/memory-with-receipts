"""Abstract base classes and data types for document parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Section:
    """A logical section within a parsed document.

    For markdown, this represents a heading-delimited block.
    For plain text, this represents a paragraph or contiguous block.
    """

    title: str
    level: int  # 0 = root/no-heading, 1 = h1, 2 = h2, etc.
    content: str
    start_char: int
    end_char: int
    heading_path: str = ""  # e.g. "Architecture > Core Design > Decisions"
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """The result of parsing a raw source into structured sections.

    This is the intermediate representation between raw input and chunks.
    """

    title: str
    content: str  # full normalized text
    sections: list[Section] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract interface for source-type-specific document parsers."""

    @abstractmethod
    def can_parse(self, source_type: str) -> bool:
        """Return True if this parser handles the given source type."""
        ...

    @abstractmethod
    def parse(self, raw_content: str | bytes, metadata: dict | None = None) -> ParsedDocument:
        """Parse raw content into a structured ParsedDocument.

        Args:
            raw_content: The raw text or bytes to parse.
            metadata: Optional metadata about the source (title, uri, etc.).

        Returns:
            A ParsedDocument with sections, titles, and character offsets.

        Raises:
            ParsingError: If the content cannot be parsed.
        """
        ...
