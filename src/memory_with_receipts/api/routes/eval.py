"""POST /v1/eval/run — Run the golden dataset evaluation.

Loads the golden JSONL dataset, runs each case through GenerationService,
applies all metrics, and returns a structured EvalReport as JSON.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from memory_with_receipts.api.eval_schemas import (
    CaseResultSchema,
    EvalRunRequest,
    EvalRunResponse,
    MetricResultSchema,
)
from memory_with_receipts.api.rag_dependencies import get_rag_db_session
from memory_with_receipts.core.logging import get_logger
from memory_with_receipts.evaluation.dataset import load_golden_dataset
from memory_with_receipts.evaluation.runner import EvalRunner
from memory_with_receipts.llm.generation import GenerationService

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["eval"])

# Default dataset path — resolved relative to the project root
_DEFAULT_DATASET = "eval_datasets/golden_v1.jsonl"


def _get_generation_service(request: Request) -> GenerationService:
    """Dependency: retrieve GenerationService from app state."""
    return request.app.state.generation_service


@router.post("/eval/run", response_model=EvalRunResponse)
def eval_run(
    body: EvalRunRequest,
    request: Request,
    session: Annotated[Session, Depends(get_rag_db_session)],
    service: Annotated[GenerationService, Depends(_get_generation_service)],
) -> EvalRunResponse:
    """Run the golden dataset evaluation and return a structured report."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    # Resolve dataset path
    dataset_path_str = body.dataset_path or _DEFAULT_DATASET
    # Resolve relative to the project root (two levels up from this file)
    if not Path(dataset_path_str).is_absolute():
        project_root = Path(__file__).parent.parent.parent.parent.parent
        resolved_path = project_root / dataset_path_str
    else:
        resolved_path = Path(dataset_path_str)

    logger.info(
        "eval_run_started",
        correlation_id=correlation_id,
        dataset_path=str(resolved_path),
        top_k=body.top_k,
    )

    try:
        cases = load_golden_dataset(resolved_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    runner = EvalRunner(
        generation_service=service,
        session=session,
        top_k=body.top_k,
    )
    report = runner.run_all(cases, dataset_path=str(resolved_path))

    logger.info(
        "eval_run_completed",
        correlation_id=correlation_id,
        total_cases=report.total_cases,
        passed=report.passed,
        pass_rate=report.pass_rate,
    )

    # Serialize to response schema
    case_schemas = [
        CaseResultSchema(
            case_id=cr.case_id,
            query=cr.query,
            answer=cr.answer,
            is_insufficient=cr.is_insufficient,
            passed=cr.passed,
            metrics=[
                MetricResultSchema(
                    name=m.name,
                    passed=m.passed,
                    score=m.score,
                    detail=m.detail,
                )
                for m in cr.metrics
            ],
        )
        for cr in report.cases
    ]

    return EvalRunResponse(
        correlation_id=correlation_id,
        dataset_path=report.dataset_path,
        total_cases=report.total_cases,
        passed=report.passed,
        failed=report.failed,
        pass_rate=report.pass_rate,
        per_metric_pass_rate=report.per_metric_pass_rate,
        generated_at=report.generated_at,
        cases=case_schemas,
    )
