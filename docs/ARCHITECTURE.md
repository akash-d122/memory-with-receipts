# Production-Grade RAG System with Receipts — Architecture

## Goal

Build a production-grade RAG system where every answer includes traceable receipts: source provenance, retrieval reasoning, freshness metadata, and evaluation-backed reliability. The system has two first-class verticals: operational memory (database events) and document RAG (text, markdown, PDF, web).

## Architectural thesis

Generic RAG often fails because it returns text chunks without enough accountability. This project treats memory as an operational system, not just a vector search demo.

Every factual answer must include receipts. If the system cannot attach reliable receipts, it must return an insufficient-evidence response instead of guessing.

A receipt includes:

- what was recalled (quoted evidence)
- where it came from (source ID, title, URI)
- when it was captured (timestamps, freshness)
- how confident the system is (confidence, trust score)
- whether newer or conflicting evidence exists (status: active/stale/contradicted)
- why this evidence was selected (retrieval score, reason codes)
- what verification metadata exists (embedding model, extraction method)

## High-level components

```text
SRE Dashboard (Next.js Frontend)
        |
        v
FastAPI Boundary (Backend Router)
        |
        +-- Operational memory vertical        +-- Document RAG vertical
        |     +-> event ingestion               |     +-> document ingestion
        |     +-> deterministic evidence        |     |     +-> parsers (text/md/pdf/web)
        |     |   extraction                    |     |     +-> chunking (fixed/structure/semantic)
        |     +-> memory creation/update        |     |     +-> embedding (local/API)
        |     +-> provenance receipts           |     |     +-> storage (documents/chunks)
        |     |                                 |
        |     +-> deterministic retrieval       |     +-> hybrid retrieval
        |     +-> reason codes                  |     |     +-> vector search (pgvector)
        |                                       |     |     +-> keyword search (tsvector)
        |                                       |     |     +-> RRF fusion
        |                                       |     |     +-> metadata filters
        |                                       |     |     +-> receipt construction
        |                                       |     |
        +-- DBE Diagnostic Agent (ReAct / ADK)  |     +-> reranking (cross-encoder)
        |     +-> tool execution                |
        |     |   (sql/bash/metrics)            +-- Generation service
        |     +-> sandbox parsing               |     +-> context assembly
        |     +-> Slack / GChat notification    |     +-> LLM prompt construction
        |                                       |     +-> citation extraction
        +-- Evaluation framework                |     +-> receipt block
              +-> golden datasets               |
              +-> deterministic metrics         +-- Shared
              +-> regression tracking                 +-> embeddings (ingestion + query)
              +-> evaluation reports                  +-> provider interfaces
                                                      +-> structured logging

PostgreSQL + pgvector
        +-> source_records, evidence_records    (operational memory)
        +-> memory_records, provenance_links    (operational memory)
        +-> documents, chunks                   (document RAG)
        +-> chunk_embeddings                    (vector storage)
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

## Phase 1 operational intelligence vertical slice

The first real memory slice is now focused on database operations and reliability events rather than generic chatbot memory.

Operational event path:

```text
Operational Alert/Event
  -> deterministic evidence extraction
  -> operational memory record creation/update
  -> provenance links as receipts
  -> deterministic retrieval scoring
  -> retrieval explanation reason codes
```

Operational domain examples:

- database alarms
- replication lag incidents
- failover events
- storage saturation
- CPU saturation
- connection exhaustion
- deadlock spikes
- remediation notes
- runbook references

Operational tables:

- `source_records`: immutable raw operational events, including raw JSON payloads.
- `evidence_records`: deterministic extracted dimensions and metrics.
- `memory_records`: higher-level operational incident memory abstractions.
- `provenance_links`: receipt links from memory to exact source/evidence support.

The current deterministic memory identity is intentionally simple:

```text
environment:service:host_or_cluster:category
```

Example:

```text
prod:postgres-prod:db-01:replication_lag
```

Retrieval scoring currently favors explainability over intelligence. Signals include:

- same service
- same host
- same environment
- same alert category
- same severity
- evidence key overlap
- recent incident

To avoid noisy operational false positives, retrieval only returns memories with at least one meaningful operational anchor: same service, same host, same alert category, or evidence-key overlap. Weak context signals such as environment, severity, or recency help rank an already-related candidate, but they are not enough by themselves to return a match.

The operational API surface is intentionally small:

- `POST /operational-memory/events`: validate and ingest one structured operational event.
- `POST /operational-memory/retrieval`: return matched memories, score, reason codes, freshness metadata, and provenance/source references.

Idempotency strategy:

- `source_identifier` is the strict idempotency key for operational event ingestion.
- Duplicate/retried events return the existing source/memory/provenance graph.
- Duplicate retries do not create new evidence, do not create new provenance links, and do not increase trust score.
- The database unique constraint on `source_records.source_identifier` is the final safety net.

This strategy is deliberately conservative. It prevents duplicate webhook retries from corrupting trust while avoiding fuzzy incident merging before real operational examples justify that complexity.

No LLM extraction, embeddings, vector search, agents, queues, or microservices are used in this slice.

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
- Single-agent setup: Only the DBE Diagnostic Agent is supported, not general multi-agent systems.
- No automatic contradiction detection in v1.
- No complex permission model in v1.
- No separate vector database in v1.
- No LLM-based fact extraction in the core pipeline (operational memory extraction remains deterministic).

## What not to build yet

- User accounts and teams.
- OAuth.
- Graph database.
- Agent marketplace integrations.
- Enterprise portals (SRE Dashboard is focused solely on metrics and diagnostics).
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
