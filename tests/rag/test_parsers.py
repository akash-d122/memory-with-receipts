"""Tests for text and markdown parsers."""

import pytest

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.markdown_parser import MarkdownParser
from memory_with_receipts.ingestion.parsers.text_parser import TextParser


class TestTextParser:
    """Tests for TextParser."""

    def setup_method(self) -> None:
        self.parser = TextParser()

    def test_can_parse_text_types(self) -> None:
        assert self.parser.can_parse("text") is True
        assert self.parser.can_parse("txt") is True
        assert self.parser.can_parse("plain_text") is True
        assert self.parser.can_parse("markdown") is False
        assert self.parser.can_parse("pdf") is False

    def test_single_paragraph(self) -> None:
        text = "This is a single paragraph with some content."
        result = self.parser.parse(text, metadata={"title": "Test"})

        assert result.title == "Test"
        assert result.content == text
        assert len(result.sections) == 1
        assert result.sections[0].content == text
        assert result.sections[0].title == "Paragraph 1"

    def test_multiple_paragraphs(self) -> None:
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here."
        result = self.parser.parse(text, metadata={"title": "Multi"})

        assert len(result.sections) == 3
        assert result.sections[0].content == "First paragraph here."
        assert result.sections[1].content == "Second paragraph here."
        assert result.sections[2].content == "Third paragraph here."

    def test_character_offsets_are_tracked(self) -> None:
        text = "First paragraph.\n\nSecond paragraph."
        result = self.parser.parse(text)

        first = result.sections[0]
        second = result.sections[1]

        # Verify offsets point to correct locations in original text
        assert text[first.start_char : first.end_char] == "First paragraph."
        assert text[second.start_char : second.end_char] == "Second paragraph."

    def test_empty_text_returns_no_sections(self) -> None:
        result = self.parser.parse("", metadata={"title": "Empty"})
        assert result.sections == []

    def test_whitespace_only_returns_no_sections(self) -> None:
        result = self.parser.parse("   \n\n   \n  ")
        assert result.sections == []

    def test_bytes_input_decoded(self) -> None:
        text_bytes = b"Hello from bytes."
        result = self.parser.parse(text_bytes, metadata={"title": "Bytes"})
        assert result.title == "Bytes"
        assert len(result.sections) == 1
        assert result.sections[0].content == "Hello from bytes."

    def test_invalid_bytes_raises_parsing_error(self) -> None:
        bad_bytes = b"\xff\xfe invalid utf-8 \x80\x81"
        with pytest.raises(ParsingError, match="Cannot decode"):
            self.parser.parse(bad_bytes)

    def test_default_title_is_untitled(self) -> None:
        result = self.parser.parse("Some text.")
        assert result.title == "Untitled"

    def test_metadata_passed_through(self) -> None:
        meta = {"title": "Custom", "author": "Test", "tags": ["a", "b"]}
        result = self.parser.parse("Content.", metadata=meta)
        assert result.metadata == meta


class TestMarkdownParser:
    """Tests for MarkdownParser."""

    def setup_method(self) -> None:
        self.parser = MarkdownParser()

    def test_can_parse_markdown_types(self) -> None:
        assert self.parser.can_parse("markdown") is True
        assert self.parser.can_parse("md") is True
        assert self.parser.can_parse("text") is False
        assert self.parser.can_parse("pdf") is False

    def test_extracts_title_from_h1(self) -> None:
        md = "# My Document Title\n\nSome content here."
        result = self.parser.parse(md)
        assert result.title == "My Document Title"

    def test_heading_hierarchy_preserved(self) -> None:
        md = """# Top Level

Introduction content.

## Section A

Section A content.

### Subsection A.1

Subsection content.

## Section B

Section B content.
"""
        result = self.parser.parse(md)

        # Find sections by title
        titles = [s.title for s in result.sections]
        assert "Top Level" in titles
        assert "Section A" in titles
        assert "Subsection A.1" in titles
        assert "Section B" in titles

    def test_heading_paths_built_correctly(self) -> None:
        md = """# Doc

## Architecture

### Core Design

Content here.

### API Design

More content.

## Testing

Test info.
"""
        result = self.parser.parse(md)

        # Build a dict of title -> heading_path
        paths = {s.title: s.heading_path for s in result.sections}

        assert paths["Doc"] == "Doc"
        assert paths["Architecture"] == "Doc > Architecture"
        assert paths["Core Design"] == "Doc > Architecture > Core Design"
        assert paths["API Design"] == "Doc > Architecture > API Design"
        assert paths["Testing"] == "Doc > Testing"

    def test_preamble_before_first_heading(self) -> None:
        md = """Some preamble text before any heading.

# First Heading

Content after heading.
"""
        result = self.parser.parse(md)

        assert result.sections[0].title == "Preamble"
        assert "preamble text" in result.sections[0].content

    def test_no_headings_returns_single_section(self) -> None:
        md = "Just plain text with no headings at all."
        result = self.parser.parse(md)

        assert len(result.sections) == 1
        assert result.sections[0].title == "Content"
        assert result.sections[0].level == 0

    def test_empty_markdown_returns_no_sections(self) -> None:
        result = self.parser.parse("")
        assert result.sections == []

    def test_heading_levels_tracked(self) -> None:
        md = "# H1\n\nContent\n\n## H2\n\nContent\n\n### H3\n\nContent"
        result = self.parser.parse(md)

        levels = {s.title: s.level for s in result.sections}
        assert levels["H1"] == 1
        assert levels["H2"] == 2
        assert levels["H3"] == 3

    def test_metadata_title_overrides_h1(self) -> None:
        md = "# Auto Title\n\nContent."
        result = self.parser.parse(md, metadata={"title": "Custom Override"})
        assert result.title == "Custom Override"

    def test_bytes_input_decoded(self) -> None:
        md_bytes = b"# Hello\n\nWorld."
        result = self.parser.parse(md_bytes)
        assert result.title == "Hello"
        assert len(result.sections) >= 1

    def test_character_offsets_are_valid(self) -> None:
        md = "# Title\n\nContent under title.\n\n## Second\n\nMore content."
        result = self.parser.parse(md)

        for section in result.sections:
            assert section.start_char >= 0
            assert section.end_char > section.start_char
            assert section.end_char <= len(md)
