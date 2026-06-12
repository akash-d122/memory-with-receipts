"""Pydantic schemas for POST /v1/eval/run."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvalRunRequest(BaseModel):
    """Request body for POST /v1/eval/run."""

    dataset_path: str | None = Field(
        default=None,
        description=(
            "Path to golden JSONL dataset. Defaults to the bundled "
            "'eval_datasets/golden_v1.jsonl'."
        ),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of context chunks to retrieve per query.",
    )


class MetricResultSchema(BaseModel):
    """Serialized result for a single metric."""

    name: str
    passed: bool
    score: float
    detail: str


class CaseResultSchema(BaseModel):
    """Serialized result for a single golden case."""

    case_id: str
    query: str
    answer: str
    is_insufficient: bool
    passed: bool
    metrics: list[MetricResultSchema]


class EvalRunResponse(BaseModel):
    """Response for POST /v1/eval/run."""

    correlation_id: str
    dataset_path: str
    total_cases: int
    passed: int
    failed: int
    pass_rate: float
    per_metric_pass_rate: dict[str, float]
    generated_at: str
    cases: list[CaseResultSchema]
