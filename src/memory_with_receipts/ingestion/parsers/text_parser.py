"""Plain text parser.

Splits text into paragraph-based sections, tracking character offsets.
A paragraph is a contiguous block separated by one or more blank lines.
"""

from __future__ import annotations

import re

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.base import BaseParser, ParsedDocument, Section


class TextParser(BaseParser):
    """Parses plain text into paragraph-based sections."""

    def can_parse(self, source_type: str) -> bool:
        return source_type in ("text", "txt", "plain_text")

    def parse(self, raw_content: str | bytes, metadata: dict | None = None) -> ParsedDocument:
        metadata = metadata or {}

        if isinstance(raw_content, bytes):
            try:
                text = raw_content.decode("utf-8")
            except UnicodeDecodeError as e:
                raise ParsingError(f"Cannot decode text content: {e}") from e
        else:
            text = raw_content

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        title = metadata.get("title", "Untitled")
        sections = self._extract_paragraphs(text)

        return ParsedDocument(
            title=title,
            content=text,
            sections=sections,
            metadata=metadata,
        )

    def _extract_paragraphs(self, text: str) -> list[Section]:
        """Split text into paragraphs on blank lines, tracking char offsets."""
        sections: list[Section] = []
        # Split on two or more newlines (with optional whitespace between)
        paragraph_pattern = re.compile(r"\n\s*\n")

        # Find paragraph boundaries
        parts = paragraph_pattern.split(text)
        current_pos = 0

        for _, part in enumerate(parts):
            stripped = part.strip()
            if not stripped:
                # Advance past whitespace/blank sections
                current_pos = text.find(part, current_pos) + len(part)
                continue

            # Find exact position in original text
            start = text.find(part, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(part)

            sections.append(
                Section(
                    title=f"Paragraph {len(sections) + 1}",
                    level=0,
                    content=stripped,
                    start_char=start,
                    end_char=end,
                    heading_path="",
                )
            )
            current_pos = end

        return sections
