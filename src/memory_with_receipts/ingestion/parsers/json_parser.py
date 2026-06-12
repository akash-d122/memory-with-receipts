from __future__ import annotations

import json

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.base import BaseParser, ParsedDocument, Section


class JSONParser(BaseParser):
    """Parses JSON content into flattened key-value sections."""

    def can_parse(self, source_type: str) -> bool:
        return source_type.lower() in ("json",)

    def parse(self, raw_content: str | bytes, metadata: dict | None = None) -> ParsedDocument:
        metadata = metadata or {}

        if isinstance(raw_content, bytes):
            try:
                content_str = raw_content.decode("utf-8")
            except UnicodeDecodeError as e:
                raise ParsingError(f"Cannot decode JSON content: {e}") from e
        else:
            content_str = raw_content

        try:
            parsed_data = json.loads(content_str)
        except json.JSONDecodeError as e:
            raise ParsingError(f"Invalid JSON content: {e}") from e

        sections: list[Section] = []
        full_text_parts = []
        current_pos = 0

        # Determine if we have a list of objects or a single object
        items = parsed_data if isinstance(parsed_data, list) else [parsed_data]

        for idx, item in enumerate(items):
            # Flatten item
            flat_dict: dict[str, str] = {}
            self._flatten(item, flat_dict)

            # Determine title for this section
            title = None
            # Look for common identifying fields
            if isinstance(item, dict):
                for candidate in ("name", "title", "id", "key"):
                    if candidate in item and isinstance(item[candidate], (str, int)):
                        title = str(item[candidate])
                        break
            if not title:
                # Look in flattened fields too just in case
                for candidate in ("name", "title", "id", "key"):
                    if candidate in flat_dict:
                        title = flat_dict[candidate]
                        break
            if not title:
                title = f"Item {idx + 1}"

            # Format flattened dict as key: value lines
            lines = [f"{k}: {v}" for k, v in flat_dict.items()]
            content_block = "\n".join(lines)

            if idx > 0:
                full_text_parts.append("\n\n")
                current_pos += 2

            start_char = current_pos
            full_text_parts.append(content_block)
            end_char = start_char + len(content_block)
            current_pos = end_char

            sections.append(
                Section(
                    title=title,
                    level=0,
                    content=content_block,
                    start_char=start_char,
                    end_char=end_char,
                    heading_path="",
                    metadata={"index": idx, **(item if isinstance(item, dict) else {})},
                )
            )

        full_text = "".join(full_text_parts)
        doc_title = metadata.get("title", "Untitled")

        return ParsedDocument(
            title=doc_title,
            content=full_text,
            sections=sections,
            metadata=metadata,
        )

    def _flatten(self, val: any, res: dict[str, str], prefix: str = "") -> None:
        """Recursively flatten dictionary or list into a single-level dictionary."""
        if isinstance(val, dict):
            for k, v in val.items():
                new_key = f"{prefix}.{k}" if prefix else k
                self._flatten(v, res, new_key)
        elif isinstance(val, list):
            for i, v in enumerate(val):
                new_key = f"{prefix}[{i}]" if prefix else str(i)
                self._flatten(v, res, new_key)
        else:
            # Primitive values
            if val is not None:
                res[prefix] = str(val)
            else:
                res[prefix] = ""
