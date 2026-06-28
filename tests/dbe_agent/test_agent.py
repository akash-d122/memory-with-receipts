"""Unit tests for the DBE Diagnostic Agent ReAct Loop."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from memory_with_receipts.db.base import Base
from memory_with_receipts.dbe_agent.agent import DBEDiagnosticAgent, parse_action
from memory_with_receipts.llm.base import BaseLLMProvider, GenerationResult


class CustomMockLLM(BaseLLMProvider):
    """Mock LLM returning a canned sequence of ReAct turns."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.idx = 0

    @property
    def model_name(self) -> str:
        return "mock-react-llm"

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, prompt: str) -> GenerationResult:
        if self.idx < len(self.responses):
            ans = self.responses[self.idx]
            self.idx += 1
        else:
            ans = "RCA Report:\n# Max Steps Hit\nNo RCA."
        return GenerationResult(
            answer=ans,
            raw_prompt=prompt,
            model=self.model_name,
            provider=self.provider_name,
        )


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    return session_factory()


def test_parse_action_extraction_varieties():
    # Positional string
    assert parse_action('Action: execute_bash("df -h")') == ("execute_bash", "df -h")
    # Named argument with query=
    assert parse_action('Action: execute_sql(query="SELECT 1;")') == ("execute_sql", "SELECT 1;")
    # Positionals for query_pmm_metrics
    assert parse_action('Action: query_pmm_metrics("cpu", 30)') == ("query_pmm_metrics", ("cpu", 30))
    # Positional string with single quotes
    assert parse_action("Action: execute_bash('free -m')") == ("execute_bash", "free -m")
    # Positional with no quotes
    assert parse_action("Action: uptime()") == ("uptime", "")


async def test_agent_diagnose_loop_completes_successfully():
    react_sequence = [
        # Turn 1: Call execute_bash
        "Thought: Checking disk space first.\nAction: execute_bash('df -h')",
        # Turn 2: Call execute_sql
        "Thought: Disk is healthy. Let's query connection limits.\nAction: execute_sql('SHOW max_connections;')",
        # Turn 3: Compile Report
        (
            "Thought: All checks completed. Compiling final report.\n"
            "RCA Report:\n"
            "# PostgreSQL Diagnostics Report\n"
            "## Root Cause Analysis\n"
            "Disk space is at 96% usage but connection limits are healthy.\n"
            "## Preventative Recommendations\n"
            "Monitor storage usage trends.\n"
            "## Remediation Steps\n"
            "Run disk cleanup or enable storage autoscaling."
        ),
    ]

    llm = CustomMockLLM(react_sequence)
    agent = DBEDiagnosticAgent(llm)

    with _session() as session:
        report = await agent.diagnose(session, query="PostgreSQLReplicationLagCritical", max_steps=5)

        assert report.is_successful is True
        assert len(report.steps) == 3
        
        # Step 1 asserts
        assert report.steps[0].action_tool == "execute_bash"
        assert report.steps[0].action_argument == "df -h"
        assert "Filesystem" in report.steps[0].observation

        # Step 2 asserts
        assert report.steps[1].action_tool == "execute_sql"
        assert report.steps[1].action_argument == "SHOW max_connections;"

        # Step 3 asserts
        assert report.steps[2].action_tool is None
        assert "# PostgreSQL Diagnostics Report" in report.rca_report
        assert "disk cleanup" in report.rca_report


async def test_agent_diagnose_handles_blocked_commands_gracefully():
    react_sequence = [
        # Turn 1: Call dangerous bash command
        "Thought: Deleting system files to free up disk.\nAction: execute_bash('rm -rf /')",
        # Turn 2: Compile report indicating failure
        (
            "Thought: Tool call failed due to sandbox constraints.\n"
            "RCA Report:\n"
            "# Diagnostics Terminated\n"
            "## Root Cause Analysis\n"
            "Unable to perform diagnostic deletion.\n"
            "## Preventative Recommendations\n"
            "None.\n"
            "## Remediation Steps\n"
            "Investigate manual access."
        ),
    ]

    llm = CustomMockLLM(react_sequence)
    agent = DBEDiagnosticAgent(llm)

    with _session() as session:
        report = await agent.diagnose(session, query="PostgreSQLHighMemoryUsage", max_steps=3)

        assert report.is_successful is True
        assert len(report.steps) == 2
        assert report.steps[0].action_tool == "execute_bash"
        assert "ERROR: Command validation failed" in report.steps[0].observation
        assert "# Diagnostics Terminated" in report.rca_report
