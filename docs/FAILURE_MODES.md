# Failure Modes to Watch Early

## Retrieval without evidence

Risk: The system returns plausible facts but cannot show where they came from.

Control: Retrieval responses must include evidence/source metadata.

## Old information outranks new information

Risk: The system recalls stale facts because they are semantically similar.

Control: Track captured timestamps, valid ranges, and recency scoring.

## Contradictions are hidden

Risk: The system returns one side of a conflict without warning.

Control: Add contradiction status and later explicit contradiction links.

## Confidence becomes fake certainty

Risk: Confidence is treated as truth instead of a signal.

Control: Store confidence as metadata and expose it transparently.

## Vector search hides system behavior

Risk: Embeddings return results that are hard to debug.

Control: Keep score breakdowns and structured filters visible.

## Overengineering kills learning speed

Risk: Building infrastructure instead of understanding memory reliability.

Control: No microservices, no Kubernetes, no complex queues until there is real pressure.

## Duplicate source events break ingestion

Risk: Monitoring systems retry webhooks or resend the same alert identifier, causing duplicate source conflicts.

Control: `source_identifier` is the strict ingestion idempotency key. Duplicate/retried source events return the existing source, memory, evidence count, and provenance count without inserting new rows or increasing trust score. The unique database constraint remains the final guard against concurrent duplicate ingestion.

Residual risk: If the monitoring system emits different identifiers for the same underlying incident, the current slice will still store separate events. That is intentional for now; fuzzy time-window dedupe can merge real incidents incorrectly.

## Operational memory keys over-split or under-group incidents

Risk: `environment:service:host_or_cluster:category` is explainable, but it may split one incident across hosts or merge unrelated recurring alerts.

Control: Keep the key deterministic for now, then add tested grouping rules when real examples show pressure.

## Trust score inflates from repeated noisy alerts

Risk: Repeated alerts from one noisy source can increase trust even when they do not represent independent evidence.

Control: Later weight trust by source independence, severity, verification status, and recurrence windows.

## Runbook and remediation notes go stale

Risk: Stored runbook references or remediation notes may become outdated after infrastructure changes.

Control: Track freshness, last-seen timestamps, and later verification events for operational references.

## Chunking quality degrades retrieval and generation

Risk: Naive character-count splitting severs context across chunk boundaries. Answers lose coherence because the LLM receives fragments.

Control: Use structure-aware chunking that respects paragraph and heading boundaries. Store heading paths and section titles in chunk metadata. Test chunking quality with golden dataset retrieval recall.

## Embedding model changes break retrieval silently

Risk: Changing the embedding model or dimension without re-embedding existing chunks produces meaningless similarity scores.

Control: Store `embedding_model`, `embedding_dimension`, and `embedding_provider` per chunk in the database. Validate query embedding dimensions match stored chunk dimensions before search. Flag stale embeddings when the configured model changes.

## Citation hallucination in generated answers

Risk: The LLM generates `[1]` or `[2]` citation markers that do not map to any retrieved chunk, creating fake receipts.

Control: Post-process generated text to validate every `[N]` marker maps to a real retrieved chunk. Strip or flag invalid citations. Track citation validity rate as an evaluation metric.

## Retrieval precision vs recall tradeoff is invisible

Risk: Hybrid retrieval returns too many low-quality chunks (high recall, low precision), diluting the context window. Or returns too few chunks (high precision, low recall), missing relevant evidence.

Control: Expose score breakdowns in every retrieval result. Track context precision and context recall as separate evaluation metrics. Tune hybrid fusion weights against golden dataset results.

## LLM/embedding provider logic leaks into application services

Risk: Provider-specific API calls, response formats, or error handling spread through retrieval, generation, and ingestion code, making provider switching expensive.

Control: Use provider interfaces (`BaseLLMProvider`, `BaseEmbeddingProvider`) from the start. Tests use mock providers. Real providers are injected via configuration.

## Evaluation metrics become hand-wavy without golden datasets

Risk: "RAGAS-style metrics" sound good on a README but produce noisy or meaningless scores without curated test data and clear baselines.

Control: Start with deterministic metrics on hand-curated golden datasets. Establish baselines before adding LLM-judge metrics. Track regression against baselines in CI.
