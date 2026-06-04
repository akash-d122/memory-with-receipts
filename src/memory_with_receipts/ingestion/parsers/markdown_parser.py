"""Markdown parser.

Structure-aware: preserves heading hierarchy, extracts sections by
heading levels (#, ##, ###), and tracks heading paths like
"Architecture > Core Design > Decisions".
"""

from __future__ import annotations

import re

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.base import BaseParser, ParsedDocument, Section

# Matches markdown headings: # Title, ## Title, ### Title, etc.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)$", re.MULTILINE)


class MarkdownParser(BaseParser):
    """Parses Markdown into heading-delimited sections with hierarchy."""

    def can_parse(self, source_type: str) -> bool:
        return source_type in ("markdown", "md")

    def parse(self, raw_content: str | bytes, metadata: dict | None = None) -> ParsedDocument:
        metadata = metadata or {}

        if isinstance(raw_content, bytes):
            try:
                text = raw_content.decode("utf-8")
            except UnicodeDecodeError as e:
                raise ParsingError(f"Cannot decode markdown content: {e}") from e
        else:
            text = raw_content

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        title = metadata.get("title") or self._extract_title(text) or "Untitled"
        sections = self._extract_sections(text)

        return ParsedDocument(
            title=title,
            content=text,
            sections=sections,
            metadata=metadata,
        )

    def _extract_title(self, text: str) -> str | None:
        """Extract the first h1 heading as the document title."""
        match = re.search(r"^#\s+(.+?)$", text, re.MULTILINE)
        return match.group(1).strip() if match else None

    def _extract_sections(self, text: str) -> list[Section]:
        """Split markdown into sections based on heading boundaries."""
        headings = list(_HEADING_RE.finditer(text))

        if not headings:
            # No headings: treat entire document as one section
            stripped = text.strip()
            if not stripped:
                return []
            return [
                Section(
                    title="Content",
                    level=0,
                    content=stripped,
                    start_char=0,
                    end_char=len(text),
                    heading_path="",
                )
            ]

        sections: list[Section] = []
        # Track heading stack for building heading paths
        heading_stack: list[tuple[int, str]] = []  # (level, title)

        # Content before first heading (preamble)
        if headings[0].start() > 0:
            preamble = text[: headings[0].start()].strip()
            if preamble:
                sections.append(
                    Section(
                        title="Preamble",
                        level=0,
                        content=preamble,
                        start_char=0,
                        end_char=headings[0].start(),
                        heading_path="",
                    )
                )

        for i, match in enumerate(headings):
            level = len(match.group(1))
            heading_title = match.group(2).strip()

            # Update heading stack: pop entries at same level or deeper
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading_title))

            # Build heading path
            heading_path = " > ".join(title for _, title in heading_stack)

            # Section content: from after heading line to next heading or end
            content_start = match.end()
            content_end = headings[i + 1].start() if i + 1 < len(headings) else len(text)

            section_content = text[content_start:content_end].strip()

            sections.append(
                Section(
                    title=heading_title,
                    level=level,
                    content=section_content,
                    start_char=match.start(),
                    end_char=content_end,
                    heading_path=heading_path,
                )
            )

        return sections
