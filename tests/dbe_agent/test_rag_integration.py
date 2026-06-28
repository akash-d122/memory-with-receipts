"""Unit and integration tests for RAG runbook-augmented diagnostics in DBE agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from memory_with_receipts.db.base import Base
from memory_with_receipts.dbe_agent.agent import DBEDiagnosticAgent
from memory_with_receipts.llm.base import BaseLLMProvider, GenerationResult
from memory_with_receipts.rag.search_service import SearchResultData


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


async def test_agent_diagnose_injects_runbook_context():
    """Verify that runbook_context is correctly injected into the system prompt."""
    react_sequence = [
        "Thought: Checking logs.\nRCA Report:\n# Incident Resolved\nDone."
    ]
    llm = CustomMockLLM(react_sequence)
    agent = DBEDiagnosticAgent(llm)

    # We patch generate to inspect the prompt it receives
    original_generate = llm.generate
    captured_prompts = []

    def mock_generate(prompt: str) -> GenerationResult:
        captured_prompts.append(prompt)
        return original_generate(prompt)

    llm.generate = mock_generate

    runbook_chunks = [
        "Runbook Chunk A: Check replica status.",
        "Runbook Chunk B: Restart pg_pool if connections leak."
    ]

    with _session() as session:
        report = await agent.diagnose(
            session,
            query="PostgreSQLHighConnections",
            max_steps=1,
            runbook_context=runbook_chunks
        )

        assert report.is_successful is True
        assert len(captured_prompts) == 1
        prompt_text = captured_prompts[0]

        # Check system prompt includes the runbook context header and chunks
        assert "Relevant Runbook Knowledge:" in prompt_text
        assert "- Runbook Chunk A: Check replica status." in prompt_text
        assert "- Runbook Chunk B: Restart pg_pool if connections leak." in prompt_text


async def test_agent_diagnose_backward_compatibility():
    """Verify agent functions correctly without runbook_context."""
    react_sequence = [
        "Thought: Checking logs.\nRCA Report:\n# Incident Resolved\nDone."
    ]
    llm = CustomMockLLM(react_sequence)
    agent = DBEDiagnosticAgent(llm)

    original_generate = llm.generate
    captured_prompts = []

    def mock_generate(prompt: str) -> GenerationResult:
        captured_prompts.append(prompt)
        return original_generate(prompt)

    llm.generate = mock_generate

    with _session() as session:
        report = await agent.diagnose(session, query="PostgreSQLHighConnections", max_steps=1)

        assert report.is_successful is True
        assert len(captured_prompts) == 1
        prompt_text = captured_prompts[0]

        # System prompt should NOT contain the runbook context headers/chunks
        assert "Relevant Runbook Knowledge:" not in prompt_text



def test_api_diagnose_route_queries_search_service(request):
    """Test that the /v1/dbe/diagnose API route queries the search service and filters by RRF score."""
    from memory_with_receipts.api.app import create_app
    from memory_with_receipts.api.dependencies import get_operational_db_session
    from memory_with_receipts.api.rag_dependencies import get_rag_db_session
    from memory_with_receipts.db.base import Base
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    app = create_app()

    def override_db_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_operational_db_session] = override_db_session
    app.dependency_overrides[get_rag_db_session] = override_db_session

    client = TestClient(app)

    mock_search_results = [
        SearchResultData(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="WAL Guide",
            source_type="markdown",
            uri="file://wal.md",
            chunk_index=0,
            content="Check WAL size limit",
            section_title="WAL",
            heading_path="WAL",
            start_char=0,
            end_char=20,
            vector_score=0.9,
            keyword_score=0.8,
            rrf_score=0.05,  # Matches: > 0.01
            reason_codes=["vector_match"],
        ),
        SearchResultData(
            chunk_id="chunk-2",
            document_id="doc-2",
            document_title="Operational Memory Doc",
            source_type="operational-memory",  # Excluded: source_type matches operational-memory
            uri="file://op.md",
            chunk_index=0,
            content="Operational event content",
            section_title="Op",
            heading_path="Op",
            start_char=0,
            end_char=25,
            vector_score=0.9,
            keyword_score=0.8,
            rrf_score=0.08,
            reason_codes=["vector_match"],
        ),
        SearchResultData(
            chunk_id="chunk-3",
            document_id="doc-3",
            document_title="Irrelevant Guide",
            source_type="markdown",
            uri="file://irrelevant.md",
            chunk_index=0,
            content="Low score markdown chunk",
            section_title="Irrelevant",
            heading_path="Irrelevant",
            start_char=0,
            end_char=24,
            vector_score=0.1,
            keyword_score=0.05,
            rrf_score=0.005,  # Excluded: < 0.01 RRF score
            reason_codes=["vector_match"],
        ),
    ]

    # Patch the SearchService.search method
    with patch("memory_with_receipts.rag.search_service.SearchService.search", return_value=mock_search_results) as mock_search:
        # We also need to patch get_dbe_llm_provider to return mock provider
        from memory_with_receipts.llm.mock import MockLLMProvider
        from memory_with_receipts.api.routes.dbe import get_dbe_llm_provider
        canned_react = (
            "Thought: Diagnostic step\n"
            "RCA Report:\n"
            "# Resolved"
        )
        mock_llm = MockLLMProvider(answer_template=canned_react)

        app.dependency_overrides[get_dbe_llm_provider] = lambda: mock_llm

        response = client.post(
            "/v1/dbe/diagnose",
            json={"query": "PostgreSQLHighConnections", "max_steps": 2}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should only contain "Check WAL size limit" (chunk-1 matches both filters)
        # chunk-2 has source_type "operational-memory" (excluded)
        # chunk-3 has rrf_score 0.005 (excluded)
        assert data["runbook_context_used"] == ["Check WAL size limit"]
        mock_search.assert_called_once()
