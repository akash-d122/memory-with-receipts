<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# AI-Assisted Service

* [Service Overview](https://dashboards.gitlab.net/d/ai-assisted-main/ai-assisted)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22ai-assisted%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::AI-Assisted"


<!-- END_MARKER -->

## Summary

AI Assisted is a dedicated Rails fleet that provides an AI Abstraction Layer in front of [AI Gateway](../ai-gateway/README.md). It handles AI-specific requests that are often long running and depend on external services (such as Vertex AI and Anthropic). To prevent these requests from occupying Puma workers on the main fleet, potentially impacting performance, AI Assisted runs on an isolated fleet to safely serve these endpoints without affecting core GitLab traffic.

## Architecture

For diagram, refer to [architecture blueprint](https://docs.gitlab.com/ee/development/ai_architecture.html#saas-based-ai-abstraction-layer).

## Operational Roles and Responsibilities

Currently, all traffic served by the AI Assisted service supports Code Suggestions features, such as Code Generation and Completion, which are owned by the [Code Creation Group](https://handbook.gitlab.com/handbook/engineering/ai/code-creation/). However, if additional feature teams begin contributing endpoints under /api/v4/ai_assisted in the future, service ownership may need to be reassessed.

The service is implemented across the following projects:

* [Gitlab.com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com): Kubernetes deployments, services and ingress rules
* [gitlab-haproxy](https://gitlab.com/gitlab-cookbooks/gitlab-haproxy): HAProxy routing configuration and backend pools
* [Chef Repository](https://gitlab.com/gitlab-com/gl-infra/chef-repo): Chef roles and backend IP configuration
* [gitlab-com/runbooks](https://gitlab.com/gitlab-com/runbooks): Service catalog, metrics catalog, and monitoring configuration

## Deployment

AI-Assisted Service is deployed in:

* Staging
* Production

## Regions

AI-Assisted Service is currently deployed across 3 pods in the following regions:

1. us-east1-b
1. us-east1-c
1. us-east1-d

## Performance

AI-Assisted Service includes the following SLIs/SLOs:

* [Apdex](https://dashboards.gitlab.net/d/ai-assisted-main/ai-assisted3a-overview?from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&viewPanel=panel-1407741353&orgId=1)
* [Error Rate](https://dashboards.gitlab.net/d/ai-assisted-main/ai-assisted3a-overview?from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&viewPanel=panel-2185880559&orgId=1)

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

## Links to further Documentation

* <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/24005>
