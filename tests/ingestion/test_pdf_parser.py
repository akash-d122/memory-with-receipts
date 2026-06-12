from unittest.mock import MagicMock, patch

import pytest

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.pdf_parser import PDFParser


class TestPDFParser:
    def setup_method(self) -> None:
        self.parser = PDFParser()

    def test_can_parse_pdf(self) -> None:
        assert self.parser.can_parse("pdf") is True
        assert self.parser.can_parse("PDF") is True
        assert self.parser.can_parse("txt") is False

    @patch("memory_with_receipts.ingestion.parsers.pdf_parser.PdfReader")
    def test_parse_pdf_pages(self, mock_pdf_reader) -> None:
        # Mock pages and their text extraction
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "This is page 1 content."
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "This is page 2 content."

        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page_1, mock_page_2]
        mock_pdf_reader.return_value = mock_reader_instance

        raw_bytes = b"%PDF-1.4 mock content"
        result = self.parser.parse(raw_bytes, metadata={"title": "Mock PDF"})

        assert result.title == "Mock PDF"
        assert "This is page 1 content." in result.content
        assert "This is page 2 content." in result.content
        assert len(result.sections) == 2

        sec1 = result.sections[0]
        assert sec1.title == "Page 1"
        assert sec1.content == "This is page 1 content."
        assert sec1.metadata.get("page_number") == 1

        sec2 = result.sections[1]
        assert sec2.title == "Page 2"
        assert sec2.content == "This is page 2 content."
        assert sec2.metadata.get("page_number") == 2

        # Verify character offsets
        assert result.content[sec1.start_char:sec1.end_char].strip() == sec1.content
        assert result.content[sec2.start_char:sec2.end_char].strip() == sec2.content

    def test_parse_invalid_input_type(self) -> None:
        # PDF parser expects bytes
        with pytest.raises(ParsingError, match="PDF parser requires bytes"):
            self.parser.parse("not bytes")

    @patch("memory_with_receipts.ingestion.parsers.pdf_parser.PdfReader")
    def test_parse_pdf_exception(self, mock_pdf_reader) -> None:
        mock_pdf_reader.side_effect = Exception("Invalid PDF file structure")
        with pytest.raises(ParsingError, match="Failed to parse PDF"):
            self.parser.parse(b"corrupted pdf")
