<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# CI Orchestration Service

* [Service Overview](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22ci-orchestration%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::CI Orchestration"


<!-- END_MARKER -->

## Summary

`ci-orchestration` is a **virtual service** that monitors CI/CD pipeline orchestration metrics emitted by Rails (Sidekiq workers and API endpoints). It has no dedicated infrastructure — it aggregates signals from existing services (`sidekiq`, `api`, `ci-jobs-api`, `web`) to provide a unified view of pipeline health.

The SLIs are organized around three UX-oriented service boundaries (see the [original proposal](https://gitlab.com/gitlab-org/gitlab/-/work_items/592819#note_3183484223) for details):

| Boundary | User-facing question | SLIs |
| -------- | -------------------- | ---- |
| **ci-job start** | "How quickly does my job start after I push?" | `pipeline_creation_sidekiq_*`, `pipeline_processing_sidekiq_*` |
| **ci-job execution** | "How long does my job wait for a runner?" | `shared_runner_job_queue_duration`, `non_shared_runner_job_queue_duration` |
| **ci-pipeline execution** | "Are pipelines failing for infra reasons?" | `job_infra_failure_ratio` |

## Observability

| Dashboard | UID | Purpose |
| --------- | --- | ------- |
| [ci-orchestration service overview](https://dashboards.gitlab.net/d/ci-orchestration-main) | `ci-orchestration-main` | Auto-generated SLI burn rates and error budgets |
| [Pipeline Observability](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) | `ci-orchestration-pipeline-observability` | Operational view — segmented system-vs-customer failures |
| [CI Pipeline Reliability SLIs](https://dashboards.gitlab.net/d/mgzzp76) | `mgzzp76` | Leadership view — total customer impact |

## Troubleshooting

Since `ci-orchestration` is a virtual service, troubleshooting typically involves investigating the underlying services:

1. **Check the service overview dashboard** for which SLI is degraded
2. **Identify the emitting service** — worker SLIs come from Sidekiq, job queue duration from API, failure reasons from all four service types
3. **Follow the relevant service's runbook** for the underlying issue (e.g., Sidekiq queue depth, API latency)

## Common customer-facing symptoms

When a customer or SRE reports a symptom, this table maps it to the SLIs and dashboard sections to check first.

| Customer report | What to check first | Likely SLIs |
| --- | --- | --- |
| "Pipelines stuck in `created` state" | [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — Pipeline Processing section. The state-machine workers (`Ci::InitialPipelineProcessWorker`, `PipelineProcessWorker`, `Ci::BuildFinishedWorker`, `BuildQueueWorker`) advance pipelines from `created` onward — if degraded, jobs sit in `created`. Also check the `pipelines_created` traffic-cessation alert (zero pipelines created = upstream creation broken). | `pipelines_created`, `pipeline_processing_sidekiq_queueing`, `pipeline_processing_sidekiq_execution` |
| "Pipelines slow to start after I push" | [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — Pipeline Creation section. These are the workers that build the pipeline from `.gitlab-ci.yml`. | `pipeline_creation_sidekiq_queue_duration`, `pipeline_creation_sidekiq_execution` |
| "Jobs not picking up / waiting for a runner" | [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — Job Queueing section. | `shared_runner_job_queue_duration`, `non_shared_runner_job_queue_duration` |
| "Pipelines failing for infra reasons" | [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — Job Execution section. Shows per-reason breakdown of system-caused failures. | `job_infra_failure_ratio` |

## Alerts

ci-orchestration SLO violation alerts route to `#s_verify_alerts` at S3 severity (Slack-only, no paging). The `pipelines_created` traffic cessation/absent alerts page via PagerDuty at S2 — a drop to zero pipeline creations is a strong outage signal.

For triage of worker-health alerts, start with the [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) (segmented system-vs-customer view) rather than the service overview — it surfaces the underlying degradation patterns directly.

| Alert | SLI | Type | Runbook |
| ----- | --- | ---- | ------- |
| `CiOrchestrationServicePipelineCreationSidekiqQueueDurationApdexSLOViolation` | `pipeline_creation_sidekiq_queue_duration` | Apdex | [Runbook](alerts/CiOrchestrationServicePipelineCreationSidekiqSLOViolation.md) |
| `CiOrchestrationServicePipelineCreationSidekiqExecutionApdexSLOViolation` | `pipeline_creation_sidekiq_execution` | Apdex | [Runbook](alerts/CiOrchestrationServicePipelineCreationSidekiqSLOViolation.md) |
| `CiOrchestrationServicePipelineCreationSidekiqExecutionErrorSLOViolation` | `pipeline_creation_sidekiq_execution` | Error | [Runbook](alerts/CiOrchestrationServicePipelineCreationSidekiqSLOViolation.md) |
| `CiOrchestrationServicePipelineProcessingSidekiqQueueingApdexSLOViolation` | `pipeline_processing_sidekiq_queueing` | Apdex | [Runbook](alerts/CiOrchestrationServicePipelineProcessingSidekiqSLOViolation.md) |
| `CiOrchestrationServicePipelineProcessingSidekiqExecutionApdexSLOViolation` | `pipeline_processing_sidekiq_execution` | Apdex | [Runbook](alerts/CiOrchestrationServicePipelineProcessingSidekiqSLOViolation.md) |
| `CiOrchestrationServicePipelineProcessingSidekiqExecutionErrorSLOViolation` | `pipeline_processing_sidekiq_execution` | Error | [Runbook](alerts/CiOrchestrationServicePipelineProcessingSidekiqSLOViolation.md) |
| `CiOrchestrationServiceJobInfraFailureRatioErrorSLOViolation` | `job_infra_failure_ratio` | Error | [Runbook](alerts/CiOrchestrationServiceJobInfraFailureRatioErrorSLOViolation.md) |
| `CiOrchestrationServiceSharedRunnerJobQueueDurationApdexSLOViolation` | `shared_runner_job_queue_duration` | Apdex | [Runbook](alerts/CiOrchestrationServiceJobQueueDurationApdexSLOViolation.md) |
| `CiOrchestrationServiceNonSharedRunnerJobQueueDurationApdexSLOViolation` | `non_shared_runner_job_queue_duration` | Apdex | [Runbook](alerts/CiOrchestrationServiceJobQueueDurationApdexSLOViolation.md) |
| `CiOrchestrationServicePipelinesCreatedTrafficCessation` | `pipelines_created` | Traffic cessation | Fires when the pipeline creation rate is zero for 30m (with a 1h-prior baseline of ≥ 0.167 ops/s). A drop to zero is a strong signal of a platform-wide pipeline-creation outage. Customers may report pipelines stuck in `created` state as a downstream symptom; investigate `PipelineCreationMetricsWorker` health, then the pipeline creation chain in Rails. |
| `CiOrchestrationServicePipelinesCreatedTrafficAbsent` | `pipelines_created` | Traffic absent | Fires when the `pipelines_created_total` signal disappears entirely for 30m. Usually indicates a metrics-pipeline issue (Sidekiq down, Prometheus scrape broken) rather than the underlying service being down — but verify by querying `pipelines_created_total` directly in Mimir. |

## Service Changes

* [SLI definitions](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/ci-orchestration.jsonnet)
* [Dashboard source](https://gitlab.com/gitlab-com/runbooks/-/blob/master/dashboards/ci-orchestration/)
* [Epic: CI pipeline reliability SLI rollout](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/2018)

## References

* [SLO alerting howto](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/)
* [Pipeline durations must be an SLI](https://gitlab.com/gitlab-org/gitlab/-/work_items/592819)
* [CI Reliability: Incident Mitigations, Observability Gaps & Long-Term SLI Roadmap](https://gitlab.com/gitlab-org/core-devops/planning/issues/-/work_items/47)
