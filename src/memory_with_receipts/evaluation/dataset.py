"""Golden dataset loader for the evaluation framework.

Reads a JSONL file where each line is a JSON object representing one
golden test case. Validates required fields and returns typed GoldenCase
objects.
"""

from __future__ import annotations

import json
from pathlib import Path

from memory_with_receipts.evaluation.schemas import GoldenCase

# Required fields in every golden case record
_REQUIRED_FIELDS = {
    "id",
    "query",
    "expected_source_titles",
    "must_include_terms",
    "must_not_include_terms",
    "min_citation_count",
}


def load_golden_dataset(path: Path | str) -> list[GoldenCase]:
    """Load golden test cases from a JSONL file.

    Each line must be a valid JSON object containing the required fields.
    Empty lines and lines starting with '#' are skipped.

    Args:
        path: Path to the JSONL file (absolute or relative to cwd).

    Returns:
        List of GoldenCase objects in file order.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If a line is missing required fields or is malformed JSON.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {path}")

    cases: list[GoldenCase] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_no} of {path}: {exc}"
                ) from exc

            missing = _REQUIRED_FIELDS - set(record.keys())
            if missing:
                raise ValueError(
                    f"Golden case on line {line_no} is missing required fields: "
                    f"{sorted(missing)}"
                )

            cases.append(
                GoldenCase(
                    id=str(record["id"]),
                    query=str(record["query"]),
                    expected_source_titles=list(record["expected_source_titles"]),
                    must_include_terms=list(record["must_include_terms"]),
                    must_not_include_terms=list(record["must_not_include_terms"]),
                    min_citation_count=int(record["min_citation_count"]),
                )
            )

    return cases
