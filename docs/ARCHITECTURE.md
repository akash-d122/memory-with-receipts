# Memory With Receipts Architecture

## Goal

Build a small, production-style RAG/memory system where every recalled fact can be traced back to evidence. The first version should teach systems thinking: data modeling, retrieval quality, contradiction handling, observability, and failure analysis.

## Architectural thesis

Generic RAG often fails because it returns text chunks without enough accountability. This project treats memory as an operational system, not just a vector search demo.

A memory answer should expose:

- what was recalled
- where it came from
- when it was captured
- how confident the system is
- whether newer or conflicting evidence exists
- why this evidence was selected
- what verification metadata exists

## High-level components

```text
Client / CLI / API caller
        |
        v
FastAPI boundary
        |
        +--> Ingestion service
        |       +--> source normalization
        |       +--> chunking / fact extraction later
        |       +--> source + evidence persistence
        |
        +--> Retrieval service
        |       +--> candidate search
        |       +--> recency/confidence scoring
        |       +--> contradiction filtering
        |       +--> explanation building
        |
        +--> Evaluation utilities
                +--> golden questions
                +--> expected evidence checks
                +--> regression tracking

PostgreSQL + pgvector
        +--> sources
        +--> memories
        +--> evidence records
        +--> verification events
```

## Core design decisions

### 1. Structured memory before vector-only recall

Decision: Store structured metadata beside text and embeddings.

Why: Embeddings are useful for candidate discovery, but they are not enough for reliability. Provenance, timestamps, status, confidence, and verification fields must be queryable directly.

Tradeoff: More schema work upfront. Better debugging and better content for proof-of-work.

### 2. Monolith first, modular internals

Decision: One FastAPI app with clear internal modules.

Why: You need production-style discipline without fake enterprise complexity. Microservices would add deployment and communication complexity before there is real load.

Tradeoff: Less independent scaling. Acceptable because the MVP goal is correctness and learning, not high traffic.

### 3. PostgreSQL as the system of record

Decision: Use PostgreSQL with pgvector later for vector similarity.

Why: Postgres gives relational constraints, transactions, explainable queries, and pgvector in one system.

Tradeoff: Not as specialized as a vector DB. Correct tradeoff for this stage.

### 4. Observable by default

Decision: Use structured logs and request IDs from the beginning.

Why: Reliability engineering starts with seeing what happened. Logs should answer: what request came in, what path ran, what failed, and what evidence was returned.

Tradeoff: Slight setup overhead. Worth it.

### 5. Evaluation starts small

Decision: Begin with tiny golden datasets and deterministic checks.

Why: RAG evaluation can become huge. Start with questions, expected source IDs, expected contradiction behavior, and freshness rules.

Tradeoff: Not statistically perfect. Good enough to catch regressions early.

## MVP scope

The MVP should support:

1. Health endpoint.
2. Create source records.
3. Create memory records linked to source/evidence metadata.
4. Retrieve candidate memories with explanation fields.
5. Track contradiction status manually at first.
6. Track freshness/recency using timestamps.
7. Provide basic tests for API health, config, and retrieval scoring utilities.
8. Maintain architecture notes, roadmap, and development rules.

## Request and data flow

### Ingestion flow

```text
POST /v1/sources
  -> validate source metadata
  -> persist source record
  -> return source_id

POST /v1/memories
  -> validate claim/text + source_id
  -> normalize metadata
  -> assign confidence/status/freshness fields
  -> persist memory + evidence linkage
  -> return memory_id
```

Initial simplification: ingestion can accept manually prepared text/facts. Do not build automatic document parsing yet.

### Retrieval flow

```text
POST /v1/retrieve
  -> validate query
  -> collect candidate memories
  -> score by text match first, vector similarity later
  -> adjust using confidence + recency + contradiction status
  -> return memory + receipt/explanation
```

Initial simplification: start with lexical scoring and structured metadata. Add embeddings only after the data model and tests are stable.

## Retrieval pipeline concept

1. Query normalization.
2. Candidate generation.
3. Metadata filtering:
   - active vs contradicted
   - source type
   - freshness window
4. Ranking:
   - relevance score
   - confidence score
   - recency score
   - contradiction penalty
5. Receipt construction:
   - source ID/title/URI
   - captured timestamp
   - evidence quote
   - confidence
   - contradiction status
   - explanation string
6. Response validation.

## Memory schema concepts

### Source

Represents where information came from.

Fields:

- id
- source_type: note, document, web, chat, manual, api
- title
- uri
- author optional
- captured_at
- metadata JSON

### Memory

Represents a claim/fact the system may recall.

Fields:

- id
- claim
- normalized_subject optional
- confidence
- status: active, contradicted, stale, disputed
- valid_from optional
- valid_until optional
- created_at
- updated_at

### Evidence

Links a memory to supporting original material.

Fields:

- id
- memory_id
- source_id
- quote
- location optional: page, line, chunk, timestamp
- extraction_method: manual initially
- verification_status: unverified, checked, failed

### Retrieval explanation

Not necessarily a DB table at first. It can be response metadata.

Fields:

- matched_terms
- score_breakdown
- recency_reason
- contradiction_reason
- selected_evidence_ids

## Ingestion pipeline MVP

Start intentionally manual:

1. Accept source metadata.
2. Accept memory claim and evidence quote.
3. Validate confidence range.
4. Validate contradiction status enum.
5. Persist structured records.

Later:

- document upload
- chunking
- embeddings
- automatic fact extraction
- source deduplication

## Evaluation ideas

Start with deterministic tests:

- Given a query, expected memory IDs appear in top results.
- Contradicted memories are either excluded or clearly marked.
- Newer evidence outranks older evidence when relevance is similar.
- Every returned memory includes at least one receipt.
- Retrieval response includes explanation fields.

Later add:

- golden dataset JSONL
- recall@k
- evidence precision
- contradiction detection test cases
- regression dashboard

## What to simplify intentionally

- No microservices.
- No Kubernetes.
- No background queue initially.
- No streaming responses.
- No multi-agent orchestration yet.
- No automatic contradiction detection in v1.
- No complex permission model in v1.
- No separate vector database in v1.
- No LLM-based fact extraction until schema and retrieval tests are stable.

## What not to build yet

- User accounts and teams.
- OAuth.
- Graph database.
- Agent marketplace integrations.
- Complex UI.
- Distributed tracing stack.
- Async job orchestration.
- Continuous learning loop.
- Autonomous web ingestion.
- Expensive evaluation harness.

## Critical review

The biggest risk is building a fancy RAG demo without reliable evidence behavior. The second biggest risk is overengineering before you can explain the data flow.

The correct early goal is boring but strong:

- clean schema
- testable retrieval logic
- visible decisions
- small API surface
- clear docs
- reproducible setup
