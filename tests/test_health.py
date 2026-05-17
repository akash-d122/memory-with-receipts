from fastapi.testclient import TestClient

from memory_with_receipts.api.app import create_app


def test_health_endpoint_returns_service_status():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Memory With Receipts",
        "environment": "test",
    }
