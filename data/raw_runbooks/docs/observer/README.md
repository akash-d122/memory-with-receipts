<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Development metrics collection Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22observer%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::observer"


<!-- END_MARKER -->

<!-- ## Summary -->

## Quick Links

| Reference | Link |
| --- | --- |
| Source | [gitlab-org/quality/observer](https://gitlab.com/gitlab-org/quality/observer) |
| Production endpoint | <https://dx-observer.runway.gitlab.net> |
| Environments | [Project environments](https://gitlab.com/gitlab-org/quality/observer/-/environments) |
| Releases | [Tag releases](https://gitlab.com/gitlab-org/quality/observer/-/releases) |
| Dashboard | [Grafana](https://dashboards.gitlab.net/goto/ffkgj7d0lqnswa?orgId=1) |
| Production logs (jobs) | [Cloud Logging](https://console.cloud.google.com/logs/query;query=resource.type%20%3D%20%22cloud_run_revision%22%0Aresource.labels.service_name%20%3D%20%22dx-observer%22%0AtextPayload%20%3D~%20%22ActiveJob%22%0A%20severity%3E%3DDEFAULT;storageScope=project?project=gitlab-runway-production) |
| Production logs (API) | [Cloud Logging](https://console.cloud.google.com/logs/query;query=resource.type%20%3D%20"cloud_run_revision"%0Aresource.labels.service_name%20%3D%20"dx-observer"%0AtextPayload%20%3D~%20"%5C"controller%5C":%5C"Api::V1"%0A%20severity%3E%3DDEFAULT;storageScope=project?project=gitlab-runway-production) |
| Owner | [Developer Experience](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/developer-experience/) |

## Summary

Observer is a GitLab DX data collection service. It is the ingest path for the dashboards in [`dashboards/dx/`](../../dashboards/dx/), which are ClickHouse-backed.

<!-- ## Architecture -->

## Architecture

Observer is a Ruby on Rails application deployed on [Runway](https://docs.runway.gitlab.com/) (Google Cloud Run, in the `gitlab-runway-production` GCP project).

## Service Management

Observer is fully managed from a single GitLab project: [`gitlab-org/quality/observer`](https://gitlab.com/gitlab-org/quality/observer).

Deployment is handled by [Runway](https://docs.runway.gitlab.com/):

* **Staging** deploys automatically from every push to `main` and runs in `dry-run` mode (no writes to production ClickHouse), allowing safe pre-production validation.
* **Production** deploys only on tag push pipelines. Tags are created by manually triggering the version-bump pipeline from the GitLab UI, which produces a new [Release](https://gitlab.com/gitlab-org/quality/observer/-/releases) with a changelog.

Application secrets (including the webhook authentication token and ClickHouse credentials) are stored in Rails encrypted credentials (`config/credentials.yml.enc`). The decryption key is stored in the Runway app vault entry. See the [project README](https://gitlab.com/gitlab-org/quality/observer/-/blob/main/README.md#credentials) for rotation instructions.

<!-- ## Monitoring/Alerting -->

## Monitoring/Alerting

* Service dashboard: [Grafana](https://dashboards.gitlab.net/goto/ffkgj7d0lqnswa?orgId=1)
* Downstream dashboards consuming Observer data: [`dashboards/dx/`](../../dashboards/dx/)
* Logs: see Quick Links above (staging logs use the same queries against the `gitlab-runway-staging` project).

<!-- ## Links to further Documentation -->

## Links to further Documentation

* [Observer project README](https://gitlab.com/gitlab-org/quality/observer/-/blob/main/README.md) — local development, webhook setup, credentials, mise tasks.
* [Runway documentation](https://docs.runway.gitlab.com/) — deployment platform.
* [ClickHouse Cloud runbook](../clickhouse/README.md) — downstream storage.
