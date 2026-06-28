"""DBE Diagnostics API Router.

Exposes endpoints to trigger safe ReAct database diagnostics and alert
remediation notifications.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from memory_with_receipts.api.dependencies import get_operational_db_session
from memory_with_receipts.api.rag_dependencies import get_rag_db_session, get_search_service, get_ingestion_pipeline
from memory_with_receipts.rag.search_service import SearchService
from memory_with_receipts.ingestion.pipeline import IngestionPipeline
from memory_with_receipts.memory.ingestion import ingest_operational_event
from memory_with_receipts.dbe_agent.agent import DBEDiagnosticAgent, DiagnosticStep
from memory_with_receipts.dbe_agent.notifiers import send_gchat_notification, send_slack_notification
from memory_with_receipts.llm.base import BaseLLMProvider
from memory_with_receipts.core.logging import get_logger
import uuid

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/dbe", tags=["dbe-diagnostics"])


class DBEDiagnosticsRequest(BaseModel):
    """Payload to trigger DBE agent diagnostics."""

    query: str = Field(
        ...,
        description="The incident or alert name to diagnose (e.g. 'PostgreSQLMaxConnectionsReached').",
    )
    max_steps: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum step iterations to run the ReAct diagnostic loop.",
    )


class DiagnosticStepResponse(BaseModel):
    step_number: int
    thought: str
    action_tool: str | None = None
    action_argument: str | None = None
    observation: str | None = None


class DBEDiagnosticsResponse(BaseModel):
    """Result of the DBE agent diagnostics and SRE notifications."""

    incident_title: str
    steps: list[DiagnosticStepResponse]
    rca_report: str
    is_successful: bool
    error_message: str | None = None
    slack_sent: bool = False
    gchat_sent: bool = False
    runbook_context_used: list[str] = Field(default_factory=list)
    memory_id: str | None = None
    document_id: str | None = None


def extract_category_from_query(query: str) -> str:
    q = query.lower()
    if "lag" in q or "replication" in q:
        return "replication_lag"
    if "connection" in q or "max_connections" in q:
        return "connection_exhaustion"
    if "lock" in q or "deadlock" in q:
        return "deadlock_spike"
    if "memory" in q or "swap" in q:
        return "memory_saturation"
    if "cpu" in q or "load" in q:
        return "cpu_saturation"
    if "storage" in q or "disk" in q:
        return "storage_saturation"
    return "general_diagnostics"


def get_dbe_llm_provider(request: Request) -> BaseLLMProvider:
    """Retrieve the LLM provider configured in application settings."""
    settings = request.app.state.settings
    if settings.llm_provider == "gemini":
        from memory_with_receipts.llm.gemini import GeminiLLMProvider
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.llm_model,
        )
    else:
        from memory_with_receipts.llm.mock import MockLLMProvider
        # For mock, use a template that outputs a canned ReAct loop step then the RCA Report
        canned_react = (
            "Thought: I need to check the active connection count.\n"
            "Action: execute_sql(\"SELECT COUNT(*) FROM pg_stat_activity;\")\n"
            "Observation: 480\n"
            "Thought: The connection count is extremely high. I will compile the report.\n"
            "RCA Report:\n"
            "# PostgreSQL Max Connections Reached\n"
            "## Root Cause Analysis\n"
            "Active connections reached 480/500 limits.\n"
            "## Preventative Recommendations\n"
            "Implement PgBouncer.\n"
            "## Remediation Steps\n"
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';"
        )
        return MockLLMProvider(answer_template=canned_react)


@router.post("/diagnose", response_model=DBEDiagnosticsResponse)
async def run_dbe_diagnostics(
    payload: DBEDiagnosticsRequest,
    request: Request,
    session: Annotated[Session, Depends(get_operational_db_session)],
    rag_session: Annotated[Session, Depends(get_rag_db_session)],
    search_service: Annotated[SearchService, Depends(get_search_service)],
    pipeline: Annotated[IngestionPipeline, Depends(get_ingestion_pipeline)],
    llm_provider: Annotated[BaseLLMProvider, Depends(get_dbe_llm_provider)],
) -> DBEDiagnosticsResponse:
    """Run a safe whitelisted ReAct diagnostic loop for the given incident.

    Fires notifications to Slack and Google Chat upon completion if webhooks
    are configured.
    """
    settings = request.app.state.settings
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    # Phase 2: Runbook retrieval
    runbook_context = []
    try:
        search_results = search_service.search(
            session=rag_session,
            query=payload.query,
            top_k=3,
        )
        # Filter: minimum RRF score threshold > 0.01 and exclude operational memories
        runbook_context = [
            r.content for r in search_results
            if r.source_type != "operational-memory" and r.rrf_score > 0.01
        ]
    except Exception as exc:
        logger.warning("dbe_diagnose_runbook_search_failed", query=payload.query, error=str(exc))

    agent = DBEDiagnosticAgent(llm_provider=llm_provider)

    try:
        report = await agent.diagnose(
            session,
            query=payload.query,
            max_steps=payload.max_steps,
            runbook_context=runbook_context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "dbe_diagnose_failed", "message": str(exc)},
        ) from exc

    # Format step responses safely (coercing action argument values to string)
    step_responses = []
    for step in report.steps:
        step_responses.append(
            DiagnosticStepResponse(
                step_number=step.step_number,
                thought=step.thought,
                action_tool=step.action_tool,
                action_argument=str(step.action_argument) if step.action_argument else None,
                observation=step.observation,
            )
        )

    slack_sent = False
    gchat_sent = False
    memory_id = None
    document_id = None

    if report.is_successful and report.rca_report:
        # Fire alerts to Slack and Google Chat
        slack_sent = send_slack_notification(
            settings.slack_webhook_url, report.rca_report, payload.query
        )
        gchat_sent = send_gchat_notification(
            settings.gchat_webhook_url, report.rca_report, payload.query
        )

        # Phase 3: Feed RCA Report back to Operational Memory Event Ingestion
        try:
            op_event_payload = {
                "source_type": "dbe-diagnostic",
                "source_identifier": f"dbe-{correlation_id}",
                "title": f"DBE Diagnostic: {payload.query}",
                "severity": "info",
                "environment": "prod",
                "service_name": "postgres",
                "category": extract_category_from_query(payload.query),
                "description": f"Root Cause Analysis for alert: {payload.query}",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {},
                "rca_report": report.rca_report,
                "steps": [
                    {
                        "step_number": s.step_number,
                        "thought": s.thought,
                        "action_tool": s.action_tool,
                        "action_argument": str(s.action_argument) if s.action_argument else None,
                        "observation": s.observation
                    }
                    for s in report.steps
                ]
            }
            op_result = ingest_operational_event(session, op_event_payload, correlation_id=correlation_id)
            memory_id = op_result.get("memory_record_id")
        except Exception as exc:
            logger.exception("dbe_diagnose_op_memory_ingest_failed", correlation_id=correlation_id)

        # Phase 3: Feed RCA Report back to Document RAG Pipeline Ingestion
        try:
            steps_md = []
            for s in report.steps:
                steps_md.append(f"### Step {s.step_number}: Thought\n{s.thought}")
                if s.action_tool:
                    steps_md.append(f"**Action**: `{s.action_tool}({s.action_argument})`")
                if s.observation:
                    steps_md.append(f"**Observation**:\n```\n{s.observation}\n```")
            formatted_steps = "\n\n".join(steps_md)

            markdown_content = (
                f"# Root Cause Analysis: {payload.query}\n\n"
                f"## RCA Report\n{report.rca_report}\n\n"
                f"## Diagnostic Path\n{formatted_steps}\n"
            )

            pipeline_res = pipeline.ingest(
                session=rag_session,
                raw_content=markdown_content,
                source_type="markdown",
                title=f"DBE RCA: {payload.query}",
                uri=f"dbe-rca://{correlation_id}",
                metadata={
                    "incident": payload.query,
                    "correlation_id": correlation_id,
                    "type": "rca_report"
                }
            )
            document_id = str(pipeline_res.document_id)
        except Exception as exc:
            logger.exception("dbe_diagnose_rag_ingest_failed", correlation_id=correlation_id)

    return DBEDiagnosticsResponse(
        incident_title=payload.query,
        steps=step_responses,
        rca_report=report.rca_report,
        is_successful=report.is_successful,
        error_message=report.error_message,
        slack_sent=slack_sent,
        gchat_sent=gchat_sent,
        runbook_context_used=runbook_context,
        memory_id=memory_id,
        document_id=document_id,
    )


class DBEMetricsResponse(BaseModel):
    """Database live operational telemetry metrics response."""

    database_name: str
    active_connections: int
    idle_connections: int
    total_connections: int
    max_connections: int
    lock_count: int
    blocked_connections: int
    cache_hit_ratio: float
    db_size_bytes: int
    xact_commit: int
    xact_rollback: int
    timestamp: str


@router.get("/metrics", response_model=DBEMetricsResponse)
def get_dbe_metrics(
    session: Annotated[Session, Depends(get_operational_db_session)],
) -> DBEMetricsResponse:
    """Retrieve real-time database metrics safely using read-only Postgres catalogs.

    Falls back to simulated metrics under SQLite or query failure conditions.
    """
    dialect_name = session.bind.dialect.name
    now_str = datetime.now(timezone.utc).isoformat()

    if dialect_name == "postgresql":
        try:
            # 1. Connection counts
            conn_res = session.execute(text(
                "SELECT count(*)::int as total, "
                "COALESCE(sum(case when state = 'active' then 1 else 0 end), 0)::int as active, "
                "COALESCE(sum(case when state = 'idle' then 1 else 0 end), 0)::int as idle "
                "FROM pg_stat_activity"
            )).fetchone()
            total_conn = conn_res[0] if conn_res else 1
            active_conn = conn_res[1] if conn_res else 1
            idle_conn = conn_res[2] if conn_res else 0

            max_conn_res = session.execute(text("SHOW max_connections")).fetchone()
            max_conn = int(max_conn_res[0]) if max_conn_res else 100

            # 2. Lock statistics
            lock_res = session.execute(text("SELECT count(*)::int FROM pg_locks")).scalar() or 0
            blocked_res = session.execute(text(
                "SELECT count(*)::int FROM pg_stat_activity WHERE wait_event_type IS NOT NULL"
            )).scalar() or 0

            # 3. Cache Hit Ratio
            cache_res = session.execute(text(
                "SELECT COALESCE(sum(heap_blks_read), 0)::bigint, COALESCE(sum(heap_blks_hit), 0)::bigint "
                "FROM pg_statio_user_tables"
            )).fetchone()
            heap_read = cache_res[0] if cache_res else 0
            heap_hit = cache_res[1] if cache_res else 0
            total_blks = heap_read + heap_hit
            cache_ratio = float(heap_hit) / float(total_blks) if total_blks > 0 else 0.99

            # 4. Database Size in bytes
            size_res = session.execute(text("SELECT pg_database_size(current_database())::bigint")).scalar() or 10485760

            # 5. Transaction throughput
            xact_res = session.execute(text(
                "SELECT COALESCE(xact_commit, 0)::bigint, COALESCE(xact_rollback, 0)::bigint "
                "FROM pg_stat_database WHERE datname = current_database()"
            )).fetchone()
            commits = xact_res[0] if xact_res else 1000
            rollbacks = xact_res[1] if xact_res else 0

            db_name = session.bind.url.database or "postgresql_db"

            return DBEMetricsResponse(
                database_name=db_name,
                active_connections=active_conn,
                idle_connections=idle_conn,
                total_connections=total_conn,
                max_connections=max_conn,
                lock_count=lock_res,
                blocked_connections=blocked_res,
                cache_hit_ratio=cache_ratio,
                db_size_bytes=size_res,
                xact_commit=commits,
                xact_rollback=rollbacks,
                timestamp=now_str,
            )
        except Exception:
            # Fall back to simulation if catalog query fails
            pass

    # Simulation metrics fallback (SQLite / Test/ local mock environments)
    db_name = session.bind.url.database or "sqlite_db"
    return DBEMetricsResponse(
        database_name=db_name,
        active_connections=5,
        idle_connections=12,
        total_connections=17,
        max_connections=100,
        lock_count=3,
        blocked_connections=0,
        cache_hit_ratio=0.987,
        db_size_bytes=2859008,
        xact_commit=45120,
        xact_rollback=31,
        timestamp=now_str,
    )
