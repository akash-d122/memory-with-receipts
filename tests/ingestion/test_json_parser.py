import json

import pytest

from memory_with_receipts.core.exceptions import ParsingError
from memory_with_receipts.ingestion.parsers.json_parser import JSONParser


class TestJSONParser:
    def setup_method(self) -> None:
        self.parser = JSONParser()

    def test_can_parse_json(self) -> None:
        assert self.parser.can_parse("json") is True
        assert self.parser.can_parse("JSON") is True
        assert self.parser.can_parse("txt") is False

    def test_parse_single_object(self) -> None:
        data = {
            "id": "item-123",
            "name": "Widget A",
            "details": {
                "color": "blue",
                "price": 12.99,
                "tags": ["small", "plastic"]
            }
        }
        json_str = json.dumps(data)
        result = self.parser.parse(json_str, metadata={"title": "Single Object"})

        assert result.title == "Single Object"
        assert "id: item-123" in result.content
        assert "details.color: blue" in result.content
        assert "details.price: 12.99" in result.content
        assert "details.tags[0]: small" in result.content
        
        assert len(result.sections) == 1
        sec = result.sections[0]
        assert sec.title == "Widget A"
        assert "details.color: blue" in sec.content

    def test_parse_array_of_objects(self) -> None:
        data = [
            {"id": "A", "name": "Item A", "active": True},
            {"name": "Item B", "active": False},
            {"id": "C", "description": "Item C details"}
        ]
        json_str = json.dumps(data)
        result = self.parser.parse(json_str)

        assert len(result.sections) == 3
        
        # Check titles
        assert result.sections[0].title == "Item A"  # fallback id -> name
        assert result.sections[1].title == "Item B"  # name
        assert result.sections[2].title == "C"       # id
        
        # Check metadata
        assert result.sections[0].metadata.get("index") == 0
        assert result.sections[2].metadata.get("index") == 2

        # Verify character offsets
        for sec in result.sections:
            assert result.content[sec.start_char:sec.end_char].strip() == sec.content.strip()

    def test_invalid_json_raises_error(self) -> None:
        with pytest.raises(ParsingError, match="Invalid JSON content"):
            self.parser.parse("{invalid json")

    def test_bytes_input(self) -> None:
        data_bytes = b'{"name": "Bytes Item"}'
        result = self.parser.parse(data_bytes)
        assert len(result.sections) == 1
        assert result.sections[0].title == "Bytes Item"
