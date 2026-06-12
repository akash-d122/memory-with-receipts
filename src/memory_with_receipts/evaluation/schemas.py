"""Data schemas for the evaluation framework.

All dataclasses are frozen/immutable where it makes sense to ensure
metrics cannot accidentally mutate evaluation state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GoldenCase:
    """A single golden test case loaded from the evaluation dataset.

    Attributes:
        id: Unique stable identifier for the case (e.g. 'q001').
        query: Natural language question to ask the RAG system.
        expected_source_titles: Document titles that MUST appear in retrieved
            chunks for a source_hit_rate of 1.0.
        must_include_terms: Terms that MUST appear in the generated answer
            (case-insensitive substring match).
        must_not_include_terms: Terms that MUST NOT appear in the answer.
        min_citation_count: Minimum number of valid [N] citations expected.
    """

    id: str
    query: str
    expected_source_titles: list[str]
    must_include_terms: list[str]
    must_not_include_terms: list[str]
    min_citation_count: int


@dataclass(frozen=True)
class MetricResult:
    """Result of a single metric evaluation.

    Attributes:
        name: Metric identifier (e.g. 'source_hit_rate').
        passed: True if the metric threshold was met.
        score: Numeric score in [0.0, 1.0] (or exact count for some metrics).
        detail: Human-readable explanation of the result.
    """

    name: str
    passed: bool
    score: float
    detail: str


@dataclass
class CaseResult:
    """Aggregated evaluation result for a single golden case.

    Attributes:
        case_id: The GoldenCase.id this result corresponds to.
        query: The original query string.
        answer: The LLM-generated answer.
        is_insufficient: True when the RAG system returned insufficient context.
        metrics: Individual metric results.
        passed: True only if ALL metrics passed.
        raw_data: Optional extra data for debugging (e.g. retrieved chunks).
    """

    case_id: str
    query: str
    answer: str
    is_insufficient: bool
    metrics: list[MetricResult] = field(default_factory=list)
    passed: bool = False
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalReport:
    """Aggregated evaluation report across all golden cases.

    Attributes:
        total_cases: Number of cases evaluated.
        passed: Number of cases where all metrics passed.
        failed: Number of cases where at least one metric failed.
        pass_rate: Fraction of cases that fully passed (0.0–1.0).
        per_metric_pass_rate: Pass rate broken down per metric name.
        cases: Full list of CaseResult objects.
        generated_at: ISO-8601 timestamp when the report was created.
        dataset_path: Path to the golden dataset file used.
    """

    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    per_metric_pass_rate: dict[str, float]
    cases: list[CaseResult]
    generated_at: str
    dataset_path: str = ""
