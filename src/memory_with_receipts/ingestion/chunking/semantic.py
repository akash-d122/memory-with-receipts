from __future__ import annotations

import math
import re

from memory_with_receipts.embeddings.base import BaseEmbeddingProvider
from memory_with_receipts.ingestion.chunking.base import BaseChunker, Chunk
from memory_with_receipts.ingestion.parsers.base import ParsedDocument


def _estimate_tokens(text: str) -> int:
    """Estimate token count using whitespace splitting."""
    words = text.split()
    return max(1, int(len(words) * 1.33))


def _cosine_similarity(u: list[float], v: list[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    dot_product = sum(a * b for a, b in zip(u, v, strict=False))
    norm_u = math.sqrt(sum(a * a for a in u))
    norm_v = math.sqrt(sum(a * a for a in v))
    if norm_u == 0 or norm_v == 0:
        return 0.0
    return dot_product / (norm_u * norm_v)


class SemanticChunker(BaseChunker):
    """Splits documents at sentence boundaries where similarity drops below a threshold."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider,
        similarity_threshold: float = 0.75,
        max_chunk_tokens: int = 256,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.similarity_threshold = similarity_threshold
        self.max_chunk_tokens = max_chunk_tokens

    def chunk(self, parsed_doc: ParsedDocument) -> list[Chunk]:
        content = parsed_doc.content
        if not content.strip():
            return []

        # 1. Split content into sentences and find their character offsets
        sentence_ends = re.compile(r"(?<=[.!?])\s+")
        raw_sentences = [s.strip() for s in sentence_ends.split(content) if s.strip()]
        
        sentences_with_offsets: list[tuple[str, int, int]] = []
        current_pos = 0
        for s in raw_sentences:
            start = content.find(s, current_pos)
            if start == -1:
                start = current_pos
            end = start + len(s)
            sentences_with_offsets.append((s, start, end))
            current_pos = end

        if not sentences_with_offsets:
            return []

        # 2. Batch embed all sentences
        texts = [s for s, _, _ in sentences_with_offsets]
        embeddings = self.embedding_provider.embed(texts)

        # 3. Form semantic chunks
        chunks: list[Chunk] = []
        current_sentences = [sentences_with_offsets[0]]

        for idx in range(1, len(sentences_with_offsets)):
            curr_sentence_data = sentences_with_offsets[idx]
            curr_s = curr_sentence_data[0]

            # Compute similarity with previous sentence
            sim = _cosine_similarity(embeddings[idx - 1], embeddings[idx])

            # Check token limit for proposed chunk
            proposed_text = " ".join([s for s, _, _ in current_sentences] + [curr_s])
            proposed_tokens = _estimate_tokens(proposed_text)

            if sim < self.similarity_threshold or proposed_tokens > self.max_chunk_tokens:
                # Finalize current chunk
                chunk_text = " ".join([s for s, _, _ in current_sentences])
                chunk_start = current_sentences[0][1]
                chunk_end = current_sentences[-1][2]
                chunks.append(
                    self._make_chunk(
                        text=chunk_text,
                        index=len(chunks),
                        start_char=chunk_start,
                        end_char=chunk_end,
                        parsed_doc=parsed_doc,
                    )
                )
                current_sentences = [curr_sentence_data]
            else:
                current_sentences.append(curr_sentence_data)

        # Flush remaining sentences
        if current_sentences:
            chunk_text = " ".join([s for s, _, _ in current_sentences])
            chunk_start = current_sentences[0][1]
            chunk_end = current_sentences[-1][2]
            chunks.append(
                self._make_chunk(
                    text=chunk_text,
                    index=len(chunks),
                    start_char=chunk_start,
                    end_char=chunk_end,
                    parsed_doc=parsed_doc,
                )
            )

        return chunks

    def _make_chunk(
        self,
        text: str,
        index: int,
        start_char: int,
        end_char: int,
        parsed_doc: ParsedDocument,
    ) -> Chunk:
        """Create a Chunk with token count and section/page metadata."""
        section_title = None
        heading_path = None
        page_number = None

        for section in parsed_doc.sections:
            if section.start_char <= start_char < section.end_char:
                section_title = section.title
                heading_path = section.heading_path or None
                page_number = section.metadata.get("page_number")
                break

        return Chunk(
            content=text,
            chunk_index=index,
            section_title=section_title,
            heading_path=heading_path,
            page_number=page_number,
            start_char=start_char,
            end_char=end_char,
            token_count=_estimate_tokens(text),
        )
