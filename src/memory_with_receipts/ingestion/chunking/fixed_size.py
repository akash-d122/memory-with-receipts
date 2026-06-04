"""Fixed-size token-window chunker.

Splits text into chunks of approximately `chunk_size` tokens with
`chunk_overlap` tokens of overlap between consecutive chunks.
Respects paragraph boundaries where possible to avoid mid-sentence cuts.
"""

from __future__ import annotations

from memory_with_receipts.ingestion.chunking.base import BaseChunker, Chunk
from memory_with_receipts.ingestion.parsers.base import ParsedDocument


def _estimate_tokens(text: str) -> int:
    """Estimate token count using whitespace splitting.

    A rough approximation (1 token ≈ 0.75 words). Good enough for chunking
    boundaries without requiring tiktoken as a hard dependency in this phase.
    """
    words = text.split()
    return max(1, int(len(words) * 1.33))


class FixedSizeChunker(BaseChunker):
    """Splits documents into fixed-size token windows with overlap.

    Tries to respect paragraph boundaries: if the next paragraph would exceed
    the chunk size, the current chunk is finalized. Falls back to hard splits
    only for paragraphs that are individually larger than chunk_size.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, parsed_doc: ParsedDocument) -> list[Chunk]:
        text = parsed_doc.content
        if not text.strip():
            return []

        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return []

        chunks: list[Chunk] = []
        current_parts: list[str] = []
        current_tokens = 0
        chunk_start_char = paragraphs[0][1] if paragraphs else 0

        for para_text, para_start, para_end in paragraphs:
            para_tokens = _estimate_tokens(para_text)

            # If single paragraph exceeds chunk_size, hard-split it
            if para_tokens > self.chunk_size:
                # Flush current buffer first
                if current_parts:
                    chunks.append(self._make_chunk(
                        "\n\n".join(current_parts),
                        len(chunks),
                        chunk_start_char,
                        para_start,
                        parsed_doc,
                    ))
                    current_parts = []
                    current_tokens = 0

                # Hard-split the large paragraph by words
                sub_chunks = self._hard_split(para_text, para_start)
                for sub_text, sub_start, sub_end in sub_chunks:
                    chunks.append(self._make_chunk(
                        sub_text, len(chunks), sub_start, sub_end, parsed_doc
                    ))
                chunk_start_char = para_end
                continue

            # Would adding this paragraph exceed the chunk size?
            if current_tokens + para_tokens > self.chunk_size and current_parts:
                # Finalize current chunk
                chunk_text = "\n\n".join(current_parts)
                chunks.append(self._make_chunk(
                    chunk_text, len(chunks), chunk_start_char, para_start, parsed_doc
                ))

                # Handle overlap: keep the last paragraph(s) that fit in overlap
                overlap_parts: list[str] = []
                overlap_tokens = 0
                for p in reversed(current_parts):
                    p_tokens = _estimate_tokens(p)
                    if overlap_tokens + p_tokens > self.chunk_overlap:
                        break
                    overlap_parts.insert(0, p)
                    overlap_tokens += p_tokens

                current_parts = overlap_parts
                current_tokens = overlap_tokens
                chunk_start_char = para_start  # approximate

            current_parts.append(para_text)
            current_tokens += para_tokens

        # Flush remaining
        if current_parts:
            chunk_text = "\n\n".join(current_parts)
            chunks.append(self._make_chunk(
                chunk_text, len(chunks), chunk_start_char, len(text), parsed_doc
            ))

        return chunks

    def _split_paragraphs(self, text: str) -> list[tuple[str, int, int]]:
        """Split text into (content, start_char, end_char) tuples."""
        paragraphs: list[tuple[str, int, int]] = []
        current_pos = 0

        for part in text.split("\n\n"):
            stripped = part.strip()
            if not stripped:
                current_pos += len(part) + 2  # +2 for the \n\n
                continue

            start = text.find(part, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(part)
            paragraphs.append((stripped, start, end))
            current_pos = end + 2  # skip past the \n\n separator

        return paragraphs

    def _hard_split(
        self, text: str, base_offset: int
    ) -> list[tuple[str, int, int]]:
        """Split a single large paragraph by word boundaries."""
        words = text.split()
        splits: list[tuple[str, int, int]] = []
        current_words: list[str] = []
        current_tokens = 0

        for word in words:
            word_tokens = max(1, int(1.33))  # ~1 token per word
            if current_tokens + word_tokens > self.chunk_size and current_words:
                chunk_text = " ".join(current_words)
                char_start = base_offset + text.find(current_words[0])
                char_end = char_start + len(chunk_text)
                splits.append((chunk_text, char_start, char_end))
                current_words = []
                current_tokens = 0

            current_words.append(word)
            current_tokens += word_tokens

        if current_words:
            chunk_text = " ".join(current_words)
            char_start = base_offset
            char_end = char_start + len(chunk_text)
            splits.append((chunk_text, char_start, char_end))

        return splits

    def _make_chunk(
        self,
        text: str,
        index: int,
        start_char: int,
        end_char: int,
        parsed_doc: ParsedDocument,
    ) -> Chunk:
        """Create a Chunk with token count and section metadata."""
        # Find which section this chunk belongs to
        section_title = None
        heading_path = None
        for section in parsed_doc.sections:
            if section.start_char <= start_char < section.end_char:
                section_title = section.title
                heading_path = section.heading_path or None
                break

        return Chunk(
            content=text,
            chunk_index=index,
            section_title=section_title,
            heading_path=heading_path,
            start_char=start_char,
            end_char=end_char,
            token_count=_estimate_tokens(text),
        )
