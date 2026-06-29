# Memory With Receipts

> Production-grade RAG where every answer is traceable — or not given at all.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-blue)
![Tests](https://img.shields.io/badge/tests-299%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Most RAG systems return answers. This one returns **receipts**.

If the system cannot attach a traceable receipt to its answer — exact source, retrieval score, confidence, contradiction status — it returns `"insufficient evidence"` instead of guessing. No hallucination by design, not by luck.

---

## What this is

Two first-class verticals built on the same receipt principle:

**Operational Memory (SRE domain)**
Database alarms, replication lag, failover events. Deterministic evidence extraction, idempotent ingestion, explainable retrieval scoring with reason codes.

**Document RAG**
PDF, Markdown, and web ingestion. Hybrid retrieval (vector + keyword + Reciprocal Rank Fusion). LLM generation via Gemini, strictly grounded in retrieved chunks. Every response includes the exact chunks used.

**DBE Agent (Agentic Workflow)**
A ReAct-style Database Engineer agent that autonomously diagnoses synthetic infrastructure incidents in a sandboxed environment, applies fixes, and writes remediation receipts back to operational memory.

---

## What a receipt contains

Every retrieval response includes:

| Field | Description |
|---|---|
| `chunk_text` | Exact text used — not a summary |
| `source_provenance` | Document title, URI, ingestion timestamp |
| `retrieval_scores` | Vector score, keyword score, RRF rank |
| `confidence` | Trust score + contradiction status (active / stale / disputed) |
| `section_path` | Heading path showing where in the document the chunk lives |

---

## Architecture

```
Client / CLI / API
        │
        ▼
FastAPI monolith
        │
        ├── Operational Memory vertical
        │     ├── POST /operational-memory/events   (idempotent ingestion)
        │     └── POST /operational-memory/retrieval (scored + receipts)
        │
        ├── Document RAG vertical
        │     ├── POST /v1/ingest   (PDF · Markdown · Web)
        │     ├── POST /v1/search   (hybrid retrieval + receipts)
        │     └── POST /v1/ask      (Gemini generation + citations)
        │
        ├── Evaluation
        │     └── POST /v1/eval/run (LLM-as-a-judge: precision · recall · hallucination)
        │
        └── DBE Agent
              └── ReAct loop → sandboxed execution → memory write-back

PostgreSQL + pgvector
        ├── source_records · evidence_records · memory_records · provenance_links
        └── documents · chunks · chunk_embeddings (384-dim, all-MiniLM-L6-v2)
```

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 + uv | Fast, reproducible dependency management |
| API | FastAPI (async) | Native async, automatic OpenAPI schema |
| Database | PostgreSQL + pgvector | Relational + vector in one system, ACID compliance |
| ORM | SQLAlchemy 2.0 + asyncpg | Async ORM with full Alembic migration support |
| Embeddings | sentence-transformers (MiniLM-L6-v2) | Local, CPU-friendly, 384-dim |
| Retrieval | pgvector cosine + tsvector FTS + RRF | Hybrid beats either alone |
| Reranking | NoOpReranker (CrossEncoder implemented, not default) | RRF handles fusion; cross-encoder ready for next phase |
| LLM | Google Gemini (google-genai) | Large context window, strict grounding prompt |
| Chunking | StructureAwareChunker (active) · SemanticChunker (implemented) | Section boundaries preserve document structure |
| Frontend | Next.js 16 · React 19 · TailwindCSS · Framer Motion | SRE dashboard with real-time agent oversight |
| Testing | pytest · pytest-cov · Ruff | 299 passing (119 unit · 15 integration · 165 E2E) |

---

## Quickstart

### Prerequisites

- Docker (for PostgreSQL + pgvector)
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Node.js 18+ (for the frontend dashboard)
- A Google Gemini API key

### Backend

```bash
# Clone
git clone https://github.com/your-username/memory-with-receipts.git
cd memory-with-receipts

# Copy and configure environment
cp .env.example .env
# Set GEMINI_API_KEY and DATABASE_URL in .env

# Start PostgreSQL + pgvector
docker compose up -d

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start the API
uv run uvicorn memory_with_receipts.api.app:create_app --factory --reload
```

API available at: `http://127.0.0.1:8000`
Health check: `http://127.0.0.1:8000/health`
OpenAPI docs: `http://127.0.0.1:8000/docs`

### Frontend (SRE Dashboard)

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at: `http://localhost:3000`

### Tests

```bash
# Unit tests only (no Docker required)
uv run pytest -m "not integration" -q

# All tests (requires Docker running)
uv run pytest -q
```

---

## API reference

### Operational Memory

```
POST /operational-memory/events      Ingest a structured operational event (idempotent)
POST /operational-memory/retrieval   Retrieve memories with scores, reason codes, receipts
```

### Document RAG

```
POST /v1/ingest     Ingest documents (PDF · Markdown · Web URL)
POST /v1/search     Hybrid retrieval — returns chunks with full receipt metadata
POST /v1/ask        RAG generation — Gemini answer + inline source citations
```

### Evaluation

```
POST /v1/eval/run   Run LLM-as-a-judge evaluation (precision · recall · hallucination rate)
```

---

## Key design decisions

**Receipt enforcement over generation.** If retrieved chunks score below the confidence threshold, the LLM call is skipped entirely. The system returns `"insufficient evidence"` rather than hallucinating.

**Hybrid retrieval over vector-only.** Vector search captures semantic similarity. Keyword search captures exact terminology. RRF fusion merges both rankings. Neither alone is sufficient for production retrieval.

**Monolith with modular internals.** One FastAPI app, clear internal module boundaries. No microservices overhead before there is real load.

**Deterministic operational memory.** The SRE vertical uses no LLM for extraction. Evidence dimensions are extracted deterministically from structured event payloads. Explainability is guaranteed.

**Sandboxed agentic execution.** The DBE agent operates in an isolated simulation environment. Tool calls, infrastructure responses, and fix verification are all synthetic — safe to run, safe to test, safe to demo.

---

## Documentation

| Doc | Contents |
|---|---|
| `docs/ARCHITECTURE.md` | Component design, tradeoffs, data flow |
| `docs/ROADMAP.md` | Phased implementation plan |
| `docs/DEVELOPMENT_RULES.md` | TDD discipline, AI-assisted coding guidelines |
| `docs/FAILURE_MODES.md` | Known risks and mitigating controls |

---

## Philosophy

> Keep it small. Make it correct. Make it explainable.

Every answer has receipts. If it cannot show receipts, it does not answer.

---

## License

MIT