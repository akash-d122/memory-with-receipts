"""API tests for POST /v1/eval/run.

Uses MockLLMProvider + SQLite — no Docker, no real LLM.
The golden dataset is written to a temp file so tests are hermetic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.api.app import create_app
from memory_with_receipts.db.base import Base
from memory_with_receipts.embeddings.mock import MockEmbeddingProvider
from memory_with_receipts.llm.generation import GenerationService
from memory_with_receipts.llm.mock import MockLLMProvider
from memory_with_receipts.rag.search_service import SearchService

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_engine():
    import memory_with_receipts.rag.models  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(sqlite_engine):
    return sessionmaker(bind=sqlite_engine, expire_on_commit=False)


@pytest.fixture
def embedding_provider():
    return MockEmbeddingProvider(dimension=384)


@pytest.fixture
def generation_service(embedding_provider):
    search_service = SearchService(embedding_provider=embedding_provider)
    return GenerationService(
        llm_provider=MockLLMProvider(),
        search_service=search_service,
    )


@pytest.fixture
def client(session_factory, generation_service):
    app = create_app()
    app.state.rag_session_factory = session_factory
    app.state.generation_service = generation_service
    return TestClient(app)


def _minimal_golden_jsonl(tmp_path: Path, n: int = 2) -> Path:
    """Write a minimal golden JSONL file with n cases."""
    path = tmp_path / "golden_test.jsonl"
    records = [
        {
            "id": f"q{i:03d}",
            "query": f"test query {i}",
            "expected_source_titles": [],
            "must_include_terms": [],
            "must_not_include_terms": [],
            "min_citation_count": 0,
        }
        for i in range(n)
    ]
    with path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEvalRunEndpoint:
    def test_returns_200(self, client: TestClient, tmp_path: Path) -> None:
        dataset_path = _minimal_golden_jsonl(tmp_path, n=2)
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(dataset_path), "top_k": 3},
        )
        assert resp.status_code == 200

    def test_response_has_required_fields(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        dataset_path = _minimal_golden_jsonl(tmp_path, n=1)
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(dataset_path)},
        )
        data = resp.json()
        assert "correlation_id" in data
        assert "total_cases" in data
        assert "passed" in data
        assert "failed" in data
        assert "pass_rate" in data
        assert "per_metric_pass_rate" in data
        assert "generated_at" in data
        assert "cases" in data

    def test_total_cases_matches_dataset(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        dataset_path = _minimal_golden_jsonl(tmp_path, n=3)
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(dataset_path)},
        )
        assert resp.json()["total_cases"] == 3

    def test_passed_plus_failed_equals_total(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        dataset_path = _minimal_golden_jsonl(tmp_path, n=4)
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(dataset_path)},
        )
        data = resp.json()
        assert data["passed"] + data["failed"] == data["total_cases"]

    def test_case_results_have_metrics(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        dataset_path = _minimal_golden_jsonl(tmp_path, n=1)
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(dataset_path)},
        )
        cases = resp.json()["cases"]
        assert len(cases) == 1
        assert len(cases[0]["metrics"]) > 0
        for m in cases[0]["metrics"]:
            assert "name" in m
            assert "passed" in m
            assert "score" in m
            assert "detail" in m

    def test_404_on_missing_dataset(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": "/nonexistent/path/golden.jsonl"},
        )
        assert resp.status_code == 404

    def test_empty_dataset_returns_zero_cases(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        empty_path = tmp_path / "empty.jsonl"
        empty_path.write_text("", encoding="utf-8")
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(empty_path)},
        )
        assert resp.status_code == 200
        assert resp.json()["total_cases"] == 0

    def test_top_k_validation(self, client: TestClient, tmp_path: Path) -> None:
        dataset_path = _minimal_golden_jsonl(tmp_path)
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(dataset_path), "top_k": 0},
        )
        assert resp.status_code == 422

    def test_pass_rate_is_float_between_0_and_1(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        dataset_path = _minimal_golden_jsonl(tmp_path, n=2)
        resp = client.post(
            "/v1/eval/run",
            json={"dataset_path": str(dataset_path)},
        )
        rate = resp.json()["pass_rate"]
        assert isinstance(rate, float)
        assert 0.0 <= rate <= 1.0
