"""End-to-End integration test for RAG Ingestion and Retrieval HTTP APIs.

Launches the FastAPI app in a local uvicorn subprocess, runs ingestion requests,
deduplication checks, file uploads, Prometheus webhooks, and verifies retrieval
via search and ask APIs, then stops the server cleanly.

Usage:
    uv run --env-file .env python scripts/test_api_endpoints.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import httpx


def wait_for_server(url: str, timeout_seconds: int = 15) -> bool:
    """Poll the health endpoint until the server is ready."""
    print(f"Waiting for server at {url} to become healthy...")
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            response = httpx.get(f"{url}/health")
            if response.status_code == 200:
                print("Server is healthy and ready!")
                return True
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    return False


def main() -> None:
    print("=" * 70)
    print("  RAG HTTP API End-to-End Integration Verification")
    print("=" * 70)

    server_url = "http://127.0.0.1:8000"
    server_process = None

    # Check if a server is already running
    try:
        response = httpx.get(f"{server_url}/health")
        if response.status_code == 200:
            print("Detected an already running FastAPI server. Reusing it for tests.")
    except httpx.RequestError:
        # Start a local dev server in a subprocess
        print("Starting uvicorn server subprocess...")
        env = os.environ.copy()
        # Ensure output is unbuffered
        env["PYTHONUNBUFFERED"] = "1"
        
        server_process = subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "memory_with_receipts.api.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if not wait_for_server(server_url):
            print("ERROR: FastAPI server failed to start or become healthy.", file=sys.stderr)
            if server_process:
                server_process.terminate()
            sys.exit(1)

    client = httpx.Client(base_url=server_url, timeout=30.0)

    try:
        # ------------------------------------------------------------------
        # Test 1: JSON Ingestion
        # ------------------------------------------------------------------
        print("\n[Test 1] POST /v1/ingest - JSON ingestion...")
        payload = {
            "title": "API Verification Markdown Document",
            "content": "# Verification Guide\n\nRun instructions to verify the HTTP routes.",
            "source_type": "markdown",
            "uri": "guide://verification",
            "tags": "test,api,guide",
            "metadata": {"verified_by": "Antigravity Agent"},
        }
        res = client.post("/v1/ingest", json=payload)
        print(f"Status Code: {res.status_code}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        print("Response Payload:")
        for k, v in data.items():
            print(f"  {k}: {v}")
        
        assert data["title"] == payload["title"]
        assert data["is_duplicate"] is False
        assert data["chunk_count"] > 0
        assert data["embeddings_created"] == data["chunk_count"]
        doc_id = data["document_id"]
        print("-> Ingest JSON Success!")

        # ------------------------------------------------------------------
        # Test 2: Deduplication Check
        # ------------------------------------------------------------------
        print("\n[Test 2] POST /v1/ingest - Deduplication check...")
        res_dup = client.post("/v1/ingest", json=payload)
        print(f"Status Code: {res_dup.status_code}")
        assert res_dup.status_code == 200
        data_dup = res_dup.json()
        print("Response Payload:")
        for k, v in data_dup.items():
            print(f"  {k}: {v}")
        
        assert data_dup["document_id"] == doc_id
        assert data_dup["is_duplicate"] is True
        assert data_dup["embeddings_created"] == 0
        print("-> Deduplication check Success!")

        # ------------------------------------------------------------------
        # Test 3: Multipart File Upload Ingestion
        # ------------------------------------------------------------------
        print("\n[Test 3] POST /v1/ingest/file - Multipart file upload...")
        file_content = (
            b"# Prometheus Config Guide\n\n"
            b"This guide shows how to configure Prometheus Alertmanager webhooks."
        )
        files = {"file": ("prometheus_config.md", file_content, "text/markdown")}
        data_form = {
            "title": "Configuring Webhooks Guide",
            "uri": "guide://prometheus-webhooks",
            "tags": "prometheus,webhook,setup",
        }
        res_file = client.post("/v1/ingest/file", files=files, data=data_form)
        print(f"Status Code: {res_file.status_code}")
        assert res_file.status_code == 200, (
            f"Expected 200, got {res_file.status_code}: {res_file.text}"
        )
        data_file = res_file.json()
        print("Response Payload:")
        for k, v in data_file.items():
            print(f"  {k}: {v}")
        
        assert data_file["title"] == "Configuring Webhooks Guide"
        assert data_file["source_type"] == "markdown"  # auto-detected from .md filename
        assert data_file["is_duplicate"] is False
        print("-> Multipart File upload Success!")

        # ------------------------------------------------------------------
        # Test 4: Prometheus Webhook Ingestion
        # ------------------------------------------------------------------
        print("\n[Test 4] POST /v1/ingest/webhook/prometheus - Prometheus Webhook Ingestion...")
        webhook_payload = {
            "receiver": "memory-receipts-webhook",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "PostgreSQLHighMemoryUsage",
                        "severity": "warning",
                        "instance": "db-replica-02.prod.internal:5432",
                        "database": "production_db",
                        "team": "sre-ops",
                    },
                    "annotations": {
                        "summary": "Database RAM consumption exceeds 92%",
                        "description": (
                            "PostgreSQL RSS size on db-replica-02 is elevated at "
                            "58 GB of 64 GB total."
                        ),
                    },
                    "startsAt": "2026-06-17T12:00:00Z",
                    "generatorURL": "http://prometheus:9090/graph?g0.expr=node_memory_Active_bytes",
                }
            ],
        }
        res_webhook = client.post("/v1/ingest/webhook/prometheus", json=webhook_payload)
        print(f"Status Code: {res_webhook.status_code}")
        assert res_webhook.status_code == 200, (
            f"Expected 200, got {res_webhook.status_code}: {res_webhook.text}"
        )
        data_webhook = res_webhook.json()
        print("Response Payload:")
        print(f"  alerts_processed: {data_webhook['alerts_processed']}")
        for idx, result in enumerate(data_webhook["results"]):
            print(f"  Result [{idx}]:")
            for k, v in result.items():
                print(f"    {k}: {v}")
                
        assert data_webhook["alerts_processed"] == 1
        assert len(data_webhook["results"]) == 1
        webhook_result = data_webhook["results"][0]
        assert webhook_result["title"] == "Prometheus Alert: PostgreSQLHighMemoryUsage"
        assert webhook_result["source_type"] == "markdown"
        assert webhook_result["is_duplicate"] is False
        print("-> Prometheus Webhook Ingestion Success!")

        # ------------------------------------------------------------------
        # Test 5: Hybrid Search over Ingested Data
        # ------------------------------------------------------------------
        print("\n[Test 5] POST /v1/search - Verification search...")
        search_payload = {
            "query": "configure Prometheus Alertmanager webhooks",
            "top_k": 3,
            "source_type": "markdown",
        }
        res_search = client.post("/v1/search", json=search_payload)
        print(f"Status Code: {res_search.status_code}")
        assert res_search.status_code == 200, (
            f"Expected 200, got {res_search.status_code}: {res_search.text}"
        )
        data_search = res_search.json()
        print(f"Results Count: {data_search['total_results']}")
        for idx, item in enumerate(data_search["results"]):
            print(f"  Result [{idx}] (score={item['rrf_score']:.4f}):")
            print(f"    Document Title: {item['document_title']}")
            print(f"    Source Type: {item['source_type']}")
            print(f"    URI: {item['uri']}")
            print(f"    Snippet: {item['content'][:120]}...")
            
        assert data_search["total_results"] > 0
        first_doc = data_search["results"][0]["document_title"]
        assert "Webhooks" in first_doc or "Prometheus" in first_doc
        print("-> Hybrid search retrieve success!")

        # ------------------------------------------------------------------
        # Test 6: Answer Generation (RAG Ask)
        # ------------------------------------------------------------------
        print("\n[Test 6] POST /v1/ask - RAG query answering...")
        ask_payload = {
            "query": (
                "What instance is triggering the PostgreSQLHighMemoryUsage alert "
                "and what are its memory details?"
            ),
            "top_k": 3,
        }
        res_ask = client.post("/v1/ask", json=ask_payload)
        print(f"Status Code: {res_ask.status_code}")
        assert res_ask.status_code == 200, (
            f"Expected 200, got {res_ask.status_code}: {res_ask.text}"
        )
        data_ask = res_ask.json()
        print("-" * 60)
        print(f"Answer:\n{data_ask['answer']}")
        print("-" * 60)
        print("Citations:")
        for citation in data_ask["citations"]:
            print(
                f"  [{citation['citation_index']}] {citation['document_title']} "
                f"(RRF score: {citation['rrf_score']:.4f})"
            )
            
        assert len(data_ask["citations"]) > 0
        assert "db-replica-02.prod.internal" in data_ask["answer"] or "58 GB" in data_ask["answer"]
        print("-> RAG answer generation Success!")

        print("\n" + "=" * 70)
        print("  ALL API INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        client.close()
        if server_process:
            print("Terminating server process...")
            server_process.terminate()
            server_process.wait()
            print("Server process terminated cleanly.")


if __name__ == "__main__":
    main()
