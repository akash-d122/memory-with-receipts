from __future__ import annotations

import io

from pypdf import PdfReader

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.base import BaseParser, ParsedDocument, Section


class PDFParser(BaseParser):
    """Parses PDF binary content into page-based sections."""

    def can_parse(self, source_type: str) -> bool:
        return source_type.lower() in ("pdf",)

    def parse(self, raw_content: str | bytes, metadata: dict | None = None) -> ParsedDocument:
        metadata = metadata or {}
        if isinstance(raw_content, str):
            raise ParsingError("PDF parser requires bytes, not a string.")

        try:
            reader = PdfReader(io.BytesIO(raw_content))
            sections: list[Section] = []
            full_text_parts = []
            current_pos = 0

            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                # Normalize line endings
                page_text = page_text.replace("\r\n", "\n").replace("\r", "\n")
                
                if i > 0:
                    full_text_parts.append("\n\n")
                    current_pos += 2
                
                start_char = current_pos
                full_text_parts.append(page_text)
                end_char = start_char + len(page_text)
                current_pos = end_char

                sections.append(
                    Section(
                        title=f"Page {i + 1}",
                        level=0,
                        content=page_text,
                        start_char=start_char,
                        end_char=end_char,
                        heading_path="",
                        metadata={"page_number": i + 1},
                    )
                )

            full_text = "".join(full_text_parts)
            title = metadata.get("title", "Untitled")

            return ParsedDocument(
                title=title,
                content=full_text,
                sections=sections,
                metadata=metadata,
            )
        except Exception as e:
            if isinstance(e, ParsingError):
                raise
            raise ParsingError(f"Failed to parse PDF content: {e}") from e
