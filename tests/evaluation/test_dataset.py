"""Dataset loader tests for the evaluation framework."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory_with_receipts.evaluation.dataset import load_golden_dataset
from memory_with_receipts.evaluation.schemas import GoldenCase


def _write_jsonl(lines: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


class TestLoadGoldenDataset:
    def test_loads_valid_file(self, tmp_path: Path) -> None:
        jsonl_file = tmp_path / "golden.jsonl"
        _write_jsonl(
            [
                {
                    "id": "q001",
                    "query": "How do I access the database?",
                    "expected_source_titles": ["DB Guide"],
                    "must_include_terms": ["Teleport"],
                    "must_not_include_terms": [],
                    "min_citation_count": 1,
                }
            ],
            jsonl_file,
        )
        cases = load_golden_dataset(jsonl_file)
        assert len(cases) == 1
        assert isinstance(cases[0], GoldenCase)
        assert cases[0].id == "q001"
        assert cases[0].query == "How do I access the database?"
        assert cases[0].expected_source_titles == ["DB Guide"]
        assert cases[0].must_include_terms == ["Teleport"]
        assert cases[0].min_citation_count == 1

    def test_skips_empty_lines_and_comments(self, tmp_path: Path) -> None:
        jsonl_file = tmp_path / "golden.jsonl"
        content = (
            "# This is a comment\n"
            "\n"
            + json.dumps(
                {
                    "id": "q001",
                    "query": "test",
                    "expected_source_titles": [],
                    "must_include_terms": [],
                    "must_not_include_terms": [],
                    "min_citation_count": 0,
                }
            )
            + "\n"
        )
        jsonl_file.write_text(content, encoding="utf-8")
        cases = load_golden_dataset(jsonl_file)
        assert len(cases) == 1

    def test_loads_multiple_cases(self, tmp_path: Path) -> None:
        records = [
            {
                "id": f"q{i:03d}",
                "query": f"question {i}",
                "expected_source_titles": [],
                "must_include_terms": [],
                "must_not_include_terms": [],
                "min_citation_count": 0,
            }
            for i in range(5)
        ]
        jsonl_file = tmp_path / "golden.jsonl"
        _write_jsonl(records, jsonl_file)
        cases = load_golden_dataset(jsonl_file)
        assert len(cases) == 5

    def test_raises_on_missing_required_field(self, tmp_path: Path) -> None:
        jsonl_file = tmp_path / "golden.jsonl"
        # Missing 'query'
        _write_jsonl([{"id": "q001", "expected_source_titles": []}], jsonl_file)
        with pytest.raises(ValueError, match="missing required fields"):
            load_golden_dataset(jsonl_file)

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        jsonl_file = tmp_path / "golden.jsonl"
        jsonl_file.write_text("not valid json\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_golden_dataset(jsonl_file)

    def test_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_golden_dataset(tmp_path / "nonexistent.jsonl")

    def test_loads_bundled_golden_v1(self) -> None:
        """The committed golden_v1.jsonl must load without errors."""
        project_root = Path(__file__).parent.parent.parent
        golden_path = project_root / "eval_datasets" / "golden_v1.jsonl"
        cases = load_golden_dataset(golden_path)
        assert len(cases) >= 10
        # All IDs should be unique
        ids = [c.id for c in cases]
        assert len(ids) == len(set(ids))
