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
