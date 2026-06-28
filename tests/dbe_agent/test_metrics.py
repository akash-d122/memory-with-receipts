"""Unit tests for the PostgreSQL Live Metrics API Endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memory_with_receipts.api.app import create_app
from memory_with_receipts.api.dependencies import get_operational_db_session
from memory_with_receipts.db.base import Base


def test_dbe_metrics_endpoint_returns_valid_schema():
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

    client = TestClient(app)
    response = client.get("/v1/dbe/metrics")

    assert response.status_code == 200
    data = response.json()

    # Verify keys
    expected_keys = {
        "database_name",
        "active_connections",
        "idle_connections",
        "total_connections",
        "max_connections",
        "lock_count",
        "blocked_connections",
        "cache_hit_ratio",
        "db_size_bytes",
        "xact_commit",
        "xact_rollback",
        "timestamp",
    }
    for key in expected_keys:
        assert key in data, f"Missing key: {key}"

    # Verify type constraints
    assert isinstance(data["database_name"], str)
    assert isinstance(data["active_connections"], int) and data["active_connections"] >= 0
    assert isinstance(data["idle_connections"], int) and data["idle_connections"] >= 0
    assert isinstance(data["total_connections"], int) and data["total_connections"] >= 0
    assert isinstance(data["max_connections"], int) and data["max_connections"] >= 0
    assert isinstance(data["lock_count"], int) and data["lock_count"] >= 0
    assert isinstance(data["blocked_connections"], int) and data["blocked_connections"] >= 0
    assert isinstance(data["cache_hit_ratio"], (int, float)) and 0.0 <= data["cache_hit_ratio"] <= 1.0
    assert isinstance(data["db_size_bytes"], int) and data["db_size_bytes"] >= 0
    assert isinstance(data["xact_commit"], int) and data["xact_commit"] >= 0
    assert isinstance(data["xact_rollback"], int) and data["xact_rollback"] >= 0
    assert isinstance(data["timestamp"], str)
