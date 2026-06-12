"""EvalRunner — orchestrates evaluation across golden cases.

Usage:
    runner = EvalRunner(generation_service=svc, session=session, top_k=5)
    report = runner.run_all(cases)

The runner calls generation_service.ask() for each case, applies all
metric functions, and aggregates results into an EvalReport.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from memory_with_receipts.evaluation.metrics import (
    citation_count_check,
    context_precision,
    context_recall_at_k,
    must_include_terms_check,
    must_not_include_terms_check,
    receipt_coverage,
    source_hit_rate,
    valid_citation_coverage,
)
from memory_with_receipts.evaluation.schemas import (
    CaseResult,
    EvalReport,
    GoldenCase,
    MetricResult,
)
from memory_with_receipts.llm.generation import GenerationService

# Sentinel pattern: detect when retrieval returned no chunks
_INSUFFICIENT_ANSWER = "I do not have enough evidence"


class EvalRunner:
    """Runs evaluation cases against GenerationService and scores them.

    Args:
        generation_service: Configured GenerationService (any LLM provider).
        session: SQLAlchemy session — must be open for the lifetime of the run.
        top_k: Number of context chunks to retrieve per query.
    """

    def __init__(
        self,
        generation_service: GenerationService,
        session: Session,
        top_k: int = 5,
    ) -> None:
        self._service = generation_service
        self._session = session
        self._top_k = top_k

    def run_case(self, case: GoldenCase) -> CaseResult:
        """Evaluate a single golden case.

        Args:
            case: The GoldenCase to evaluate.

        Returns:
            CaseResult with all metric results and an overall pass/fail flag.
        """
        ask_result = self._service.ask(
            session=self._session,
            query=case.query,
            top_k=self._top_k,
        )

        metrics: list[MetricResult] = [
            # Retrieval quality
            source_hit_rate(
                citations=ask_result.citations,
                expected_titles=case.expected_source_titles,
            ),
            context_recall_at_k(
                chunks=getattr(ask_result, "_retrieved_chunks", []),
                expected_titles=case.expected_source_titles,
                k=self._top_k,
            ),
            context_precision(
                chunks=getattr(ask_result, "_retrieved_chunks", []),
                expected_titles=case.expected_source_titles,
                k=self._top_k,
            ),
            # Citation quality
            valid_citation_coverage(ask_result),
            receipt_coverage(ask_result.citations),
            citation_count_check(
                citations=ask_result.citations,
                min_citation_count=case.min_citation_count,
            ),
            # Content quality
            must_include_terms_check(
                answer=ask_result.answer,
                terms=case.must_include_terms,
            ),
            must_not_include_terms_check(
                answer=ask_result.answer,
                terms=case.must_not_include_terms,
            ),
        ]

        overall_passed = all(m.passed for m in metrics)

        return CaseResult(
            case_id=case.id,
            query=case.query,
            answer=ask_result.answer,
            is_insufficient=ask_result.is_insufficient,
            metrics=metrics,
            passed=overall_passed,
            raw_data={
                "context_chunks_used": ask_result.context_chunks_used,
                "model": ask_result.model,
                "provider": ask_result.provider,
                "retrieval_time_ms": ask_result.retrieval_time_ms,
                "generation_time_ms": ask_result.generation_time_ms,
            },
        )

    def run_all(
        self,
        cases: list[GoldenCase],
        dataset_path: str = "",
    ) -> EvalReport:
        """Evaluate all golden cases and return an aggregated EvalReport.

        Args:
            cases: List of GoldenCase objects to evaluate.
            dataset_path: Optional path label to embed in the report.

        Returns:
            EvalReport with per-metric and aggregate statistics.
        """
        case_results: list[CaseResult] = []
        for case in cases:
            case_results.append(self.run_case(case))

        total = len(case_results)
        passed_count = sum(1 for r in case_results if r.passed)
        failed_count = total - passed_count
        pass_rate = passed_count / total if total > 0 else 0.0

        # Per-metric pass rate
        per_metric: dict[str, list[bool]] = {}
        for cr in case_results:
            for m in cr.metrics:
                per_metric.setdefault(m.name, []).append(m.passed)

        per_metric_pass_rate = {
            name: sum(results) / len(results)
            for name, results in per_metric.items()
        }

        return EvalReport(
            total_cases=total,
            passed=passed_count,
            failed=failed_count,
            pass_rate=pass_rate,
            per_metric_pass_rate=per_metric_pass_rate,
            cases=case_results,
            generated_at=datetime.now(UTC).isoformat(),
            dataset_path=dataset_path,
        )
