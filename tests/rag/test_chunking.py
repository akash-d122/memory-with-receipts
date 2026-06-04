"""Tests for chunking strategies."""

from memory_with_receipts.ingestion.chunking.fixed_size import FixedSizeChunker, _estimate_tokens
from memory_with_receipts.ingestion.chunking.structure_aware import StructureAwareChunker
from memory_with_receipts.ingestion.parsers.base import ParsedDocument, Section


def _make_doc(content: str, sections: list[Section] | None = None) -> ParsedDocument:
    """Helper to create a ParsedDocument for testing."""
    return ParsedDocument(
        title="Test Doc",
        content=content,
        sections=sections or [],
        metadata={},
    )


class TestTokenEstimation:
    """Tests for the token estimation heuristic."""

    def test_empty_string(self) -> None:
        assert _estimate_tokens("") >= 1  # min 1

    def test_single_word(self) -> None:
        tokens = _estimate_tokens("hello")
        assert tokens >= 1

    def test_multi_word(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"
        tokens = _estimate_tokens(text)
        # 9 words * 1.33 ≈ 12 tokens
        assert 5 <= tokens <= 20


class TestFixedSizeChunker:
    """Tests for FixedSizeChunker."""

    def test_empty_document_returns_no_chunks(self) -> None:
        chunker = FixedSizeChunker(chunk_size=100)
        doc = _make_doc("")
        assert chunker.chunk(doc) == []

    def test_small_document_one_chunk(self) -> None:
        chunker = FixedSizeChunker(chunk_size=500)
        doc = _make_doc("A short paragraph.")
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].content == "A short paragraph."
        assert chunks[0].chunk_index == 0

    def test_chunks_have_content_hash(self) -> None:
        chunker = FixedSizeChunker(chunk_size=500)
        doc = _make_doc("Some content here.")
        chunks = chunker.chunk(doc)
        assert len(chunks) == 1
        assert len(chunks[0].content_hash) == 64  # SHA-256 hex

    def test_chunks_have_token_count(self) -> None:
        chunker = FixedSizeChunker(chunk_size=500)
        doc = _make_doc("This is a sentence with several words in it.")
        chunks = chunker.chunk(doc)
        assert chunks[0].token_count > 0

    def test_multiple_paragraphs_split_correctly(self) -> None:
        # Create 10 paragraphs, each ~20 tokens
        paragraphs = [
            f"This is paragraph number {i} with enough words to count."
            for i in range(10)
        ]
        text = "\n\n".join(paragraphs)
        chunker = FixedSizeChunker(chunk_size=50, chunk_overlap=0)
        doc = _make_doc(text)
        chunks = chunker.chunk(doc)

        # Should produce multiple chunks
        assert len(chunks) > 1
        # All chunks should have content
        for chunk in chunks:
            assert len(chunk.content.strip()) > 0

    def test_chunk_indices_are_sequential(self) -> None:
        paragraphs = [f"Paragraph {i} with some words." for i in range(5)]
        text = "\n\n".join(paragraphs)
        chunker = FixedSizeChunker(chunk_size=30, chunk_overlap=0)
        doc = _make_doc(text)
        chunks = chunker.chunk(doc)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_chunks_are_deterministic(self) -> None:
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunker = FixedSizeChunker(chunk_size=100)
        doc = _make_doc(text)

        chunks_a = chunker.chunk(doc)
        chunks_b = chunker.chunk(doc)

        assert len(chunks_a) == len(chunks_b)
        for a, b in zip(chunks_a, chunks_b, strict=True):
            assert a.content == b.content
            assert a.content_hash == b.content_hash
            assert a.chunk_index == b.chunk_index

    def test_section_metadata_inherited(self) -> None:
        text = "Content in a section."
        sections = [
            Section(
                title="My Section",
                level=1,
                content="Content in a section.",
                start_char=0,
                end_char=len(text),
                heading_path="Doc > My Section",
            )
        ]
        chunker = FixedSizeChunker(chunk_size=500)
        doc = _make_doc(text, sections=sections)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 1
        assert chunks[0].section_title == "My Section"
        assert chunks[0].heading_path == "Doc > My Section"


class TestStructureAwareChunker:
    """Tests for StructureAwareChunker."""

    def test_empty_document_returns_no_chunks(self) -> None:
        chunker = StructureAwareChunker(chunk_size=100)
        doc = _make_doc("")
        assert chunker.chunk(doc) == []

    def test_single_section_one_chunk(self) -> None:
        sections = [
            Section(
                title="Intro",
                level=1,
                content="Short introduction.",
                start_char=0,
                end_char=20,
                heading_path="Intro",
            )
        ]
        chunker = StructureAwareChunker(chunk_size=500)
        doc = _make_doc("Short introduction.", sections=sections)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 1
        assert chunks[0].section_title == "Intro"
        assert chunks[0].heading_path == "Intro"

    def test_multiple_sections_multiple_chunks(self) -> None:
        text = "# First\n\nContent A.\n\n## Second\n\nContent B."
        sections = [
            Section("First", 1, "Content A.", 0, 20, "First"),
            Section("Second", 2, "Content B.", 21, 40, "First > Second"),
        ]
        chunker = StructureAwareChunker(chunk_size=500)
        doc = _make_doc(text, sections=sections)
        chunks = chunker.chunk(doc)

        assert len(chunks) == 2
        assert chunks[0].section_title == "First"
        assert chunks[1].section_title == "Second"
        assert chunks[1].heading_path == "First > Second"

    def test_large_section_sub_chunked(self) -> None:
        # Create a section with many paragraphs that exceeds chunk_size
        paragraphs = [f"This is paragraph {i} with enough tokens to matter." for i in range(20)]
        large_content = "\n\n".join(paragraphs)
        sections = [
            Section("Big Section", 1, large_content, 0, len(large_content), "Big Section"),
        ]
        chunker = StructureAwareChunker(chunk_size=50)
        doc = _make_doc(large_content, sections=sections)
        chunks = chunker.chunk(doc)

        # Should produce multiple sub-chunks
        assert len(chunks) > 1
        # All should inherit the section metadata
        for chunk in chunks:
            assert chunk.section_title == "Big Section"
            assert chunk.heading_path == "Big Section"

    def test_no_sections_fallback(self) -> None:
        chunker = StructureAwareChunker(chunk_size=500)
        doc = _make_doc("Plain content without sections.")
        chunks = chunker.chunk(doc)

        assert len(chunks) == 1
        assert chunks[0].section_title == "Content"

    def test_chunks_are_deterministic(self) -> None:
        sections = [
            Section("A", 1, "Content A.", 0, 10, "A"),
            Section("B", 1, "Content B.", 11, 21, "B"),
        ]
        chunker = StructureAwareChunker(chunk_size=500)
        doc = _make_doc("Content A.\nContent B.", sections=sections)

        chunks_a = chunker.chunk(doc)
        chunks_b = chunker.chunk(doc)

        assert len(chunks_a) == len(chunks_b)
        for a, b in zip(chunks_a, chunks_b, strict=True):
            assert a.content == b.content
            assert a.content_hash == b.content_hash

    def test_chunk_indices_sequential(self) -> None:
        sections = [
            Section("A", 1, "Content A.", 0, 10, "A"),
            Section("B", 1, "Content B.", 11, 21, "B"),
            Section("C", 1, "Content C.", 22, 32, "C"),
        ]
        chunker = StructureAwareChunker(chunk_size=500)
        doc = _make_doc("Content A.\nContent B.\nContent C.", sections=sections)
        chunks = chunker.chunk(doc)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
