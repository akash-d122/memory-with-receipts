# Implementation Roadmap

> For behavior code: use strict TDD. Write failing tests first, then implementation.

## Phase 0: Foundation — complete

- uv project
- FastAPI app factory
- settings module
- structured logging setup
- API health endpoint
- database session foundation
- SQLAlchemy model concepts
- docs for architecture, rules, and roadmap
- pytest + Ruff setup

## Phase 1: Operational intelligence memory slice — complete

- SQLAlchemy tables for operational sources, evidence, memories, and provenance links
- Deterministic operational ingestion through `ingest_operational_event`
- Explicit dimension and metric evidence extraction
- Create or update deterministic operational memories
- Link every memory to source/evidence receipts
- Deterministic operational retrieval scoring with reason codes
- Idempotent ingestion for duplicate/retried source events
- `POST /operational-memory/events` for validated operational event ingestion
- `POST /operational-memory/retrieval` for explainable deterministic retrieval
- Freshness metadata and provenance/source references in retrieval responses
- API tests for ingestion, duplicate ingestion, retrieval explanations, and invalid payloads
- 14 tests passing

## Phase 1.5: Foundation restructure — complete

- Docker Compose for PostgreSQL + pgvector
- Extended configuration for LLM, embedding, and chunking settings
- Domain exception hierarchy
- Updated docs and paths for `prod_rag_with_receipts` repo
- pytest integration marker for Docker-dependent tests

## Phase 2: Minimal ingestion vertical slice

Goal: Ingest text and markdown into documents/chunks with source metadata.

Tasks:

1. Add SQLAlchemy tables for `documents` and `chunks`.
2. Add Alembic migration for `documents` and `chunks`.
3. Add parser interface and text/markdown parsers.
4. Add chunker interface and fixed-size/structure-aware chunkers.
5. Add ingestion pipeline orchestrator.
6. Add parser, chunking, and ingestion pipeline tests.

Exit criteria:

- Text and markdown files ingest into documents + chunks.
- Content-hash deduplication prevents re-ingestion.
- Chunk metadata includes section titles, heading paths, and character offsets.
- All tests pass with `uv run python -m pytest -q`.

## Phase 3: Embeddings and vector storage

Goal: Embed chunks with local sentence-transformers and store with pgvector.

Tasks:

1. Add embedding provider interface and local/mock implementations.
2. Add `chunk_embeddings` table with pgvector `Vector` column.
3. Add Alembic migration: enable pgvector extension, create `chunk_embeddings`, add vector index.
4. Extend ingestion pipeline with optional embedding step.
5. Add embedding provider unit tests and pgvector storage integration test.

Exit criteria:

- Mock embedding tests pass.
- pgvector storage integration test passes against Docker Postgres.
- Embedding metadata (model, dimension, provider) stored per chunk.

## Phase 4: Hybrid retrieval

Goal: Search chunks and return ranked results with receipts.

Tasks:

1. Add pgvector cosine similarity search.
2. Add Postgres tsvector/tsquery full-text search.
3. Add Reciprocal Rank Fusion hybrid merge.
4. Add metadata filters (source type, date range, status).
5. Add `NoOpReranker` as default reranker.
6. Add retrieval pipeline orchestrator.
7. Add `POST /v1/search` endpoint.
8. Add retrieval tests (unit and integration).

Exit criteria:

- `/v1/search` returns ranked chunks with receipt metadata.
- Each result includes score breakdown, provenance, and reason codes.
- Hybrid fusion correctly merges vector and keyword results.

## Phase 5: Answer generation with citations

Goal: Ask a question, receive a grounded answer with inline citations and receipt block.

Tasks:

1. Add LLM provider interface and Gemini Flash/mock implementations.
2. Add prompt templates with citation instructions.
3. Add citation extraction and receipt construction.
4. Add generation pipeline orchestrator.
5. Add `POST /v1/ask` endpoint.
6. Add generation tests (mocked LLM).

Exit criteria:

- `/v1/ask` returns answer + citations + receipts.
- Insufficient context returns "I do not have enough evidence" response.
- Every citation maps to a valid source/chunk receipt.

## Phase 6: Evaluation framework

Goal: Prove retrieval and generation quality with deterministic regression tests.

Tasks:

1. Create golden dataset (`eval_datasets/golden_v1.jsonl`).
2. Add deterministic metrics: source hit rate, context recall@k, context precision, valid citation coverage, receipt coverage, must_include_terms, must_not_include_terms.
3. Add evaluation runner and report generator.
4. Add `POST /v1/eval/run` endpoint.
5. Add evaluation guide documentation.
6. Add metric unit tests.

Exit criteria:

- Golden dataset regression test passes.
- Evaluation report generated with per-metric scores.
- CI-ready evaluation command works.

## Phase 7: Advanced features (Completed)

Goal: Mature the system with additional source types and advanced capabilities.

Tasks:

- [x] Add PDF parser.
- [x] Add web page parser.
- [x] Add JSON/API payload parser.
- [x] Add semantic chunking.
- [x] Add real cross-encoder reranker.
- [x] Add Gemini embedding provider.
- [x] Add LLM-judge metrics: faithfulness, answer relevance, claim-level coverage.
- [x] Operational memory adapter.

Exit criteria:

- [x] PDF, web, and JSON ingestion produce correct chunks.
- [x] Reranking improves retrieval precision.
- [x] LLM-judge metrics produce meaningful scores.
