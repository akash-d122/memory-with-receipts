# Development Rules

## Engineering principles

1. Build small, correct pieces.
2. Prefer explicit data flow over clever abstractions.
3. Every memory returned by retrieval must have a receipt.
4. If a behavior matters, test it.
5. If a failure mode is known, document it.
6. Do not introduce a new abstraction until duplication or pain is real.
7. Keep the API boring and understandable.

## AI-assisted engineering rules

Use AI for:

- scaffolding
- boilerplate
- test generation ideas
- documentation drafts
- refactoring suggestions
- explaining tradeoffs

Do not let AI skip:

- reading the code
- understanding request/data flow
- writing tests
- checking logs
- verifying behavior locally
- explaining why a design exists

## TDD discipline

For behavior code:

1. Write the failing test.
2. Run it and confirm the failure is meaningful.
3. Implement the smallest passing code.
4. Run the specific test.
5. Run the full test suite.
6. Refactor only while green.

## Scope control

Before adding a feature, ask:

- Does this help provenance, reliability, retrieval quality, or learning?
- Can I explain the failure mode it solves?
- Can I test it?
- Is this needed for the next milestone?

If not, do not build it yet.

## Observability rules

- Use structured logs.
- Include request IDs.
- Log important decisions, not noisy internals.
- Never log secrets.
- Errors should include enough context to debug.

## Naming rules

Prefer boring names:

- `Source`
- `Memory`
- `Evidence`
- `RetrievalResult`
- `RetrievalExplanation`

Avoid vague names:

- `Manager`
- `Processor`
- `Engine`
- `Orchestrator` unless orchestration truly exists

## Definition of done

A feature is done only when:

- tests pass
- lint passes
- docs are updated if behavior changed
- failure modes are considered
- the data flow can be explained in plain English
