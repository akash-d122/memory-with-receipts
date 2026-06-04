"""Structure-aware chunker for markdown and section-based documents.

Splits on heading/section boundaries from the parsed document.
If a single section exceeds chunk_size, it is sub-chunked by paragraphs.
Each chunk preserves the heading path from the original structure.
"""

from __future__ import annotations

from memory_with_receipts.ingestion.chunking.base import BaseChunker, Chunk
from memory_with_receipts.ingestion.chunking.fixed_size import _estimate_tokens
from memory_with_receipts.ingestion.parsers.base import ParsedDocument, Section


class StructureAwareChunker(BaseChunker):
    """Chunks documents by structural sections (headings/paragraphs).

    Each heading-delimited section becomes a chunk. Large sections are
    sub-chunked by paragraphs with token limits.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, parsed_doc: ParsedDocument) -> list[Chunk]:
        if not parsed_doc.content.strip():
            return []

        # If no sections, fall back to treating entire content as one section
        sections = parsed_doc.sections
        if not sections:
            sections = [
                Section(
                    title="Content",
                    level=0,
                    content=parsed_doc.content.strip(),
                    start_char=0,
                    end_char=len(parsed_doc.content),
                    heading_path="",
                )
            ]

        chunks: list[Chunk] = []
        for section in sections:
            section_chunks = self._chunk_section(section, len(chunks))
            chunks.extend(section_chunks)

        return chunks

    def _chunk_section(self, section: Section, base_index: int) -> list[Chunk]:
        """Convert a section into one or more chunks."""
        content = section.content.strip()
        if not content:
            return []

        tokens = _estimate_tokens(content)

        # Section fits in one chunk
        if tokens <= self.chunk_size:
            return [
                Chunk(
                    content=content,
                    chunk_index=base_index,
                    section_title=section.title,
                    heading_path=section.heading_path or None,
                    start_char=section.start_char,
                    end_char=section.end_char,
                    token_count=tokens,
                )
            ]

        # Section too large: sub-chunk by paragraphs
        return self._sub_chunk_paragraphs(section, base_index)

    def _sub_chunk_paragraphs(self, section: Section, base_index: int) -> list[Chunk]:
        """Split an oversized section into paragraph-respecting sub-chunks."""
        paragraphs = [p.strip() for p in section.content.split("\n\n") if p.strip()]
        if not paragraphs:
            return []

        chunks: list[Chunk] = []
        current_parts: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = _estimate_tokens(para)

            # Single paragraph exceeds limit — include it as its own chunk
            if para_tokens > self.chunk_size:
                if current_parts:
                    chunks.append(self._make_section_chunk(
                        "\n\n".join(current_parts),
                        base_index + len(chunks),
                        section,
                    ))
                    current_parts = []
                    current_tokens = 0

                chunks.append(self._make_section_chunk(
                    para, base_index + len(chunks), section
                ))
                continue

            if current_tokens + para_tokens > self.chunk_size and current_parts:
                chunks.append(self._make_section_chunk(
                    "\n\n".join(current_parts),
                    base_index + len(chunks),
                    section,
                ))
                current_parts = []
                current_tokens = 0

            current_parts.append(para)
            current_tokens += para_tokens

        if current_parts:
            chunks.append(self._make_section_chunk(
                "\n\n".join(current_parts),
                base_index + len(chunks),
                section,
            ))

        return chunks

    def _make_section_chunk(self, text: str, index: int, section: Section) -> Chunk:
        """Create a chunk inheriting metadata from its parent section."""
        return Chunk(
            content=text,
            chunk_index=index,
            section_title=section.title,
            heading_path=section.heading_path or None,
            start_char=section.start_char,
            end_char=section.end_char,
            token_count=_estimate_tokens(text),
        )
