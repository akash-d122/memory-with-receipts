from __future__ import annotations

import re

import html2text

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.base import BaseParser, ParsedDocument
from memory_with_receipts.ingestion.parsers.markdown_parser import MarkdownParser


class WebParser(BaseParser):
    """Parses HTML web pages into Markdown-structured sections."""

    def can_parse(self, source_type: str) -> bool:
        return source_type.lower() in ("web", "html", "htm")

    def parse(self, raw_content: str | bytes, metadata: dict | None = None) -> ParsedDocument:
        metadata = metadata or {}

        if isinstance(raw_content, bytes):
            try:
                html = raw_content.decode("utf-8")
            except UnicodeDecodeError as e:
                raise ParsingError(f"Cannot decode web content: {e}") from e
        else:
            html = raw_content

        # 1. Heuristically strip noise (nav, footer, aside, header, scripts, styles)
        html = self._strip_noise(html)

        # 2. Convert html to markdown
        try:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_emphasis = False
            h.body_width = 0  # No line wrapping to preserve paragraphs better
            markdown_content = h.handle(html)
        except Exception as e:
            raise ParsingError(f"Failed to convert HTML to Markdown: {e}") from e

        # 3. Delegate to MarkdownParser to parse the sections and build hierarchy
        md_parser = MarkdownParser()
        parsed_doc = md_parser.parse(markdown_content, metadata=metadata)
        
        return parsed_doc

    def _strip_noise(self, html: str) -> str:
        """Strip script, style, comments, and boilerplate navigation/footer tags."""
        # Strip script and style
        html = re.sub(r"<script\b[^>]*>([\s\S]*?)</script>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<style\b[^>]*>([\s\S]*?)</style>", "", html, flags=re.IGNORECASE)
        # Strip comments
        html = re.sub(r"<!--([\s\S]*?)-->", "", html)
        
        # Strip standard boilerplate containers
        html = re.sub(r"<nav\b[^>]*>([\s\S]*?)</nav>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<footer\b[^>]*>([\s\S]*?)</footer>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<header\b[^>]*>([\s\S]*?)</header>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<aside\b[^>]*>([\s\S]*?)</aside>", "", html, flags=re.IGNORECASE)
        
        return html
