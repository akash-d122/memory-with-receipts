# Evaluation Guide

> **Phase 6** — Deterministic regression testing for retrieval and generation quality.

## Overview

The evaluation framework lets you:

- Prove the RAG pipeline works correctly on a curated golden dataset
- Catch regressions when changing retrieval, prompts, or models
- Get a per-metric breakdown to pinpoint what degraded

All metrics are **deterministic and offline** — no live LLM calls during evaluation.
The `EvalRunner` calls `GenerationService.ask()` using whatever LLM provider is
configured, so in tests this is the `MockLLMProvider`, and in production you can wire
in the real Gemini provider.

---

## Quick Start

### Run via pytest (CI-friendly)

```bash
# Unit tests — no Docker needed
uv run python -m pytest tests/evaluation/ -v

# Full suite including integration tests (requires Docker)
uv run python -m pytest -v
```

### Run via the API

Start the server:

```bash
uv run uvicorn memory_with_receipts.api.app:create_app --factory --reload
```

Then POST to the eval endpoint:

```bash
curl -X POST http://localhost:8000/v1/eval/run \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_path": "eval_datasets/golden_v1.jsonl",
    "top_k": 5
  }'
```

---

## Golden Dataset Format

The dataset lives in [`eval_datasets/golden_v1.jsonl`](../eval_datasets/golden_v1.jsonl).

Each line is a JSON object:

```jsonc
{
  "id": "q001",                              // unique stable identifier
  "query": "How do I access the production database?",
  "expected_source_titles": [               // docs that MUST appear in citations
    "Internal Wiki: Database Access"
  ],
  "must_include_terms": [                   // substrings required in the answer
    "Teleport", "proxy"
  ],
  "must_not_include_terms": [               // substrings forbidden in the answer
    "plaintext password"
  ],
  "min_citation_count": 1                   // minimum [N] citations expected
}
```

### Adding Cases

1. Append a new line to `eval_datasets/golden_v1.jsonl`.
2. Choose a unique `id` (e.g. `q013`).
3. Run `uv run python -m pytest tests/evaluation/test_dataset.py -v` to validate.

---

## Metrics Reference

| Metric | What it checks | Pass condition |
|---|---|---|
| `source_hit_rate` | Expected document titles in citations | All expected titles cited |
| `context_recall_at_k` | Expected titles in top-k retrieved chunks | All expected in top-k |
| `context_precision` | Fraction of top-k chunks from expected sources | ≥ 50% relevant |
| `valid_citation_coverage` | All `[N]` markers map to real chunks | No out-of-range indices |
| `receipt_coverage` | Citations carry chunk_id, document_id, rrf_score | All receipts complete |
| `citation_count_check` | Minimum required citation count met | count ≥ min_citation_count |
| `must_include_terms` | Required terms in answer (case-insensitive) | All terms found |
| `must_not_include_terms` | Forbidden terms absent from answer | No violations |

A case **passes** only if ALL 8 metrics pass.

---

## Reading the Report

A typical `EvalRunResponse` looks like:

```json
{
  "total_cases": 12,
  "passed": 10,
  "failed": 2,
  "pass_rate": 0.833,
  "per_metric_pass_rate": {
    "source_hit_rate": 0.833,
    "context_recall_at_k": 1.0,
    "context_precision": 1.0,
    "valid_citation_coverage": 1.0,
    "receipt_coverage": 1.0,
    "citation_count_check": 0.917,
    "must_include_terms": 0.917,
    "must_not_include_terms": 1.0
  },
  "cases": [ ... ]
}
```

**How to interpret**:
- `pass_rate < 1.0` — some cases failed; check `cases[].passed == false` entries.
- Low `source_hit_rate` — retrieval isn't finding the right documents.
- Low `context_precision` — too much noise in the context window (irrelevant chunks).
- Low `must_include_terms` — the LLM answer is missing key facts.

---

## Text Report (Markdown)

You can also generate a Markdown report programmatically:

```python
from memory_with_receipts.evaluation.report import generate_text_report

report_md = generate_text_report(eval_report)
print(report_md)
# or write to disk
Path("eval_report.md").write_text(report_md)
```

---

## CI Integration

Add to your CI pipeline (GitHub Actions example):

```yaml
- name: Run evaluation
  run: uv run python -m pytest tests/evaluation/ -q
  env:
    DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/testdb
```

For a full regression check with a live DB:

```yaml
- name: Run full suite including integration
  run: uv run python -m pytest -q
```

---

## Architecture

```
eval_datasets/
  golden_v1.jsonl          ← curated golden cases

src/memory_with_receipts/evaluation/
  schemas.py               ← GoldenCase, MetricResult, CaseResult, EvalReport
  dataset.py               ← load_golden_dataset(path)
  metrics.py               ← 8 pure metric functions
  runner.py                ← EvalRunner.run_all()
  report.py                ← generate_text_report()

src/memory_with_receipts/api/
  eval_schemas.py          ← Pydantic request/response models
  routes/eval.py           ← POST /v1/eval/run

tests/evaluation/
  test_metrics.py          ← 37 pure function tests
  test_dataset.py          ← 7 loader tests
  test_runner.py           ← 9 runner tests
  test_eval_api.py         ← 9 API tests
```
