# Implementation Roadmap

> For future implementation: use strict TDD for behavior code. Write failing tests first, then implementation.

## Phase 0: Foundation - created now

- uv project
- FastAPI app factory
- settings module
- structured logging setup
- API health endpoint
- database session foundation
- SQLAlchemy model concepts
- docs for architecture, rules, and roadmap
- pytest + Ruff setup

## Phase 1: Manual memory records

Goal: Store and retrieve memory records with receipts manually.

Tasks:

1. Add SQLAlchemy tables for sources, memories, evidence.
2. Configure Alembic migrations.
3. Add Pydantic request/response schemas.
4. Implement `POST /v1/sources`.
5. Implement `POST /v1/memories`.
6. Implement `POST /v1/retrieve` with simple lexical scoring.
7. Return receipt metadata for every result.
8. Add tests for validation and retrieval behavior.

Exit criteria:

- Every retrieval result includes source and evidence.
- Contradicted memories are marked clearly.
- Tests run with `uv run pytest`.

## Phase 2: Retrieval quality

Goal: Make retrieval explainable and less naive.

Tasks:

1. Add score breakdown object.
2. Add recency scoring.
3. Add confidence scoring.
4. Add contradiction penalty.
5. Add deterministic golden test cases.
6. Add retrieval evaluation script.

Exit criteria:

- You can explain why each result ranked where it did.
- A tiny golden dataset catches ranking regressions.

## Phase 3: pgvector integration

Goal: Add embeddings after structured retrieval is stable.

Tasks:

1. Add embedding column using pgvector.
2. Add local/simple embedding provider interface.
3. Add vector candidate generation.
4. Compare lexical vs vector retrieval in tests.
5. Add fallback behavior when embeddings are missing.

Exit criteria:

- Vector search improves candidate discovery without hiding receipts.

## Phase 4: Contradiction and freshness workflows

Goal: Make memory lifecycle explicit.

Tasks:

1. Add contradiction relationship between memory records.
2. Add `supersedes_memory_id` or relation table.
3. Add freshness policies.
4. Add verification events.
5. Add tests for stale vs active vs contradicted retrieval.

Exit criteria:

- System can show newer evidence against older memory.

## Phase 5: Content and proof-of-work

Goal: Turn the project into visible evidence of systems thinking.

Outputs:

- README diagrams
- blog post: "RAG is not memory unless it has receipts"
- demo dataset
- walkthrough video
- LinkedIn technical posts
- failure mode writeup
