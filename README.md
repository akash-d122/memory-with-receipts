# Memory With Receipts

A production-style RAG/memory system where every recalled memory can show its receipts:

- original source
- timestamp
- confidence
- contradiction status
- recency/freshness
- retrieval explanation
- verification metadata

This is intentionally **not** a generic vector search demo. The goal is to learn AI reliability engineering through a small but professional system.

## Current status

Foundation initialized:

- Python + uv
- FastAPI app factory
- Pydantic settings
- structured logging
- SQLAlchemy async DB foundation
- initial memory/evidence schema concepts
- retrieval scoring utility
- pytest + Ruff
- architecture docs and roadmap

## Project location

Windows path:

```text
D:gentic_ai\memory-with-receipts
```

WSL path:

```text
/mnt/d/agentic_ai/memory-with-receipts
```

## Quickstart

```bash
cd /mnt/d/agentic_ai/memory-with-receipts
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn memory_with_receipts.api.app:create_app --factory --reload
```

Then open:

```text
http://127.0.0.1:8000/health
```

## Documentation

- `docs/ARCHITECTURE.md` - architecture, tradeoffs, MVP scope, schema concepts, pipelines
- `docs/ROADMAP.md` - staged implementation plan
- `docs/DEVELOPMENT_RULES.md` - engineering discipline and AI-assisted coding rules
- `docs/FAILURE_MODES.md` - early reliability risks

## Initial philosophy

Keep it small. Make it correct. Make it explainable.

Do not add microservices, complex queues, Kubernetes, or autonomous ingestion until the core memory/retrieval behavior is trustworthy and tested.
