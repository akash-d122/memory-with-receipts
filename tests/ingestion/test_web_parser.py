import pytest

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.web_parser import WebParser


class TestWebParser:
    def setup_method(self) -> None:
        self.parser = WebParser()

    def test_can_parse_web_types(self) -> None:
        assert self.parser.can_parse("web") is True
        assert self.parser.can_parse("html") is True
        assert self.parser.can_parse("htm") is True
        assert self.parser.can_parse("txt") is False

    def test_parse_basic_html(self) -> None:
        html = """
        <html>
            <head><title>Mock Web Page</title></head>
            <body>
                <h1>Header 1</h1>
                <p>This is the first paragraph.</p>
                <h2>Header 2</h2>
                <p>This is the second paragraph.</p>
            </body>
        </html>
        """
        result = self.parser.parse(html, metadata={"title": "Custom Web"})
        assert result.title == "Custom Web"
        assert "Header 1" in result.content
        assert "Header 2" in result.content
        
        # Verify markdown headings are extracted
        titles = [s.title for s in result.sections]
        assert "Header 1" in titles
        assert "Header 2" in titles

    def test_strip_noise_heuristics(self) -> None:
        html = """
        <html>
            <body>
                <nav>
                    <ul>
                        <li><a href="/">Home</a></li>
                        <li><a href="/about">About</a></li>
                    </ul>
                </nav>
                <header>
                    <p>Header Banner Ad</p>
                </header>
                <h1>Main Article</h1>
                <p>Actual article content goes here.</p>
                <aside>
                    <p>Sidebar advertisement or related links.</p>
                </aside>
                <footer>
                    <p>© 2026 Legal Footer text.</p>
                </footer>
            </body>
        </html>
        """
        result = self.parser.parse(html)
        
        # The content should NOT contain navigation, header ads, sidebar ads, or footer legal text.
        content_lower = result.content.lower()
        assert "legal footer" not in content_lower
        assert "banner ad" not in content_lower
        assert "sidebar advertisement" not in content_lower
        assert "home" not in content_lower
        assert "article content" in result.content

    def test_parse_bytes_input(self) -> None:
        html_bytes = b"<html><body><h1>Bytes Title</h1><p>Content</p></body></html>"
        result = self.parser.parse(html_bytes)
        assert result.title == "Bytes Title"
        assert len(result.sections) >= 1

    def test_invalid_bytes_raises_error(self) -> None:
        bad_bytes = b"\xff\xfe invalid html \x80\x81"
        with pytest.raises(ParsingError, match="Cannot decode"):
            self.parser.parse(bad_bytes)
