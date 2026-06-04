# Production-Grade RAG System with Receipts

A production-grade RAG (Retrieval-Augmented Generation) system where every answer includes traceable receipts:

- source provenance (where evidence came from)
- retrieval reasoning (why this evidence was selected)
- freshness metadata (when it was captured, recency score)
- confidence and contradiction status
- evaluation-backed reliability

This is intentionally **not** a generic vector search demo. The goal is a system where every factual answer must include receipts. If reliable receipts are unavailable, the system returns an insufficient-evidence response instead of guessing.

## Architecture

Two first-class verticals:

1. **Operational memory** — database alarms, replication lag, failover events with deterministic evidence extraction and provenance receipts
2. **Document RAG** — multi-source document ingestion, hybrid retrieval, LLM generation with inline citations and source receipts

Both share the core receipt identity: every answer is traceable to specific sources, chunks, and evidence.

## Current status

Foundation and operational memory vertical complete:

- Python 3.11 + uv
- FastAPI app factory with structured logging and correlation IDs
- SQLAlchemy async DB foundation (PostgreSQL + pgvector)
- Operational memory ingestion with deterministic evidence extraction
- Operational memory retrieval with explainable scoring and provenance receipts
- Idempotent event ingestion with source deduplication
- Docker Compose for local PostgreSQL + pgvector
- pytest + Ruff + pytest-cov
- Architecture docs and phased roadmap

## Project location

Windows path:

```text
D:\agentic_ai\prod_rag_with_receipts
```

WSL path:

```text
/mnt/d/agentic_ai/prod_rag_with_receipts
```

## Quickstart

```bash
# Start PostgreSQL + pgvector
docker compose up -d

# Install dependencies
cd /mnt/d/agentic_ai/prod_rag_with_receipts
uv sync

# Run tests
uv run python -m pytest -q

# Run linter
uv run ruff check .

# Start dev server
uv run uvicorn memory_with_receipts.api.app:create_app --factory --reload
```

Then open:

```text
http://127.0.0.1:8000/health
```

## API endpoints

### Operational memory

- `POST /operational-memory/events` — ingest structured operational events
- `POST /operational-memory/retrieval` — retrieve operational memories with receipts

### RAG pipeline (planned)

- `POST /v1/ingest` — ingest documents (text, markdown, PDF, web)
- `POST /v1/search` — hybrid retrieval with receipts
- `POST /v1/ask` — RAG generation with inline citations
- `POST /v1/eval/run` — run evaluation suite

## Documentation

- `docs/ARCHITECTURE.md` — architecture, tradeoffs, component design
- `docs/ROADMAP.md` — phased implementation plan
- `docs/DEVELOPMENT_RULES.md` — engineering discipline and AI-assisted coding rules
- `docs/FAILURE_MODES.md` — reliability risks and controls

## Philosophy

Keep it small. Make it correct. Make it explainable.

Every answer has receipts. If it cannot show receipts, it does not answer.
