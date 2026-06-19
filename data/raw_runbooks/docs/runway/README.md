<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Runway Platform Service

* [Service Overview](https://dashboards.gitlab.net/d/runway-main/runway-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22runway%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Runway"

## Logging

* [stackdriver](https://console.cloud.google.com/logs)

<!-- END_MARKER -->

## Summary

Runway is an experimental [PaaS](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/tools/runway/) for stage groups to deploy and operate services. Runway is currently built with [GitLab CI/CD](https://docs.gitlab.com/ee/development/cicd/), [GitLab Environments](https://docs.gitlab.com/ee/ci/environments/), and [GCP Cloud Run](https://cloud.google.com/run/docs/overview/what-is-cloud-run).

Not to be confused with a service that is _managed by_ Runway, e.g. [AI Gateway](../ai-gateway/README.md).

## Architecture

For diagram, refer to [architecture blueprint](https://docs.gitlab.com/ee/architecture/blueprints/runway/#architecture).

## Performance

Runway is a platform, so services determine [deployment frequency](https://gitlab.com/groups/gitlab-com/gl-infra/platform/runway/deployments/-/analytics/ci_cd?tab=deployment-frequency). Performance primarly depends on following factors:

* [Deployment pipeline failures](https://gitlab.com/gitlab-com/gl-infra/platform/runway/deployments/ai-gateway/-/pipelines?page=1&scope=all&status=failed)
* Deployment pipeline duration

Due to versioning [releases](https://gitlab.com/gitlab-com/gl-infra/platform/runway/ci-tasks/-/releases) in source projects, these SLIs can be lagging indicators that do not occur until subsequent deployment is triggered by a service.

## Scalability

Runway is a platform, so services determine workload rightsizing. Scalability primarly depends on following factors:

* Resources (CPU, Memory)
* Instances (Minimum, Maximum, Concurrency)

When investigating short-term saturation with a service deployed to Runway, you may need to scale on behalf of service owner. Long-term saturation resources are monitored with [capacity planning](#capacity-planning).

### Horizontal

By default, Runway will scale up instances to handle all incoming requests. When a service is not receiving any traffic, instances are scaled down to zero.

#### Minimum instances

The [minimum number of instances](https://cloud.google.com/run/docs/configuring/min-instances) of a service. To update, set [configuration](https://gitlab-com.gitlab.io/gl-infra/platform/runway/runwayctl/manifest.schema.html#spec_scalability_min_instances) in `runway.yml` of source project.

**Recommendation**: Use this setting if you need to reduce cold start latency for a service.

#### Maximum instances

The [maximum number of instances](https://cloud.google.com/run/docs/configuring/max-instances) of a service. To update, set [configuration](https://gitlab-com.gitlab.io/gl-infra/platform/runway/runwayctl/manifest.schema.html#spec_scalability_max_instances) in `runway.yml` of source project.

**Recommendation**: Use this setting if you need to limit the number of connections to a backing service, e.g. database.

#### Maximum instance concurrent requests

The [maximum number of concurrent requests](https://cloud.google.com/run/docs/configuring/concurrency) _per instance_ of the service. To update, set [configuration](https://gitlab-com.gitlab.io/gl-infra/platform/runway/runwayctl/manifest.schema.html#spec_scalability_max_instance_request_concurrency) in `runway.yml` of source project. When [tuning concurrency](https://cloud.google.com/run/docs/tips/general#match_memory_to_concurrency), consider increasing memory.

**Recommendation**: Use this setting if you need to either optimize cost efficiency, or limit concurrency of a service.

### Vertical

By default, Runway will provision lightweight CPU and memory resources limits of `1000m` and `512Mi`, respectively. When a resource limit is exceeded, instance is terminated.

#### Memory

The [memory limit](https://cloud.google.com/run/docs/configuring/services/memory-limits) of an instance. To update, set [configuration](https://gitlab-com.gitlab.io/gl-infra/platform/runway/runwayctl/manifest.schema.html#spec_resources_limits_memory) in `runway.yml` of source project.

#### CPU

The [CPU limit](https://cloud.google.com/run/docs/configuring/services/cpu) of an instance. To update, set [configuration](https://gitlab-com.gitlab.io/gl-infra/platform/runway/runwayctl/manifest.schema.html#spec_resources_limits_cpu) in `runway.yml` of source project.

#### CPU Boost

Provide [additional CPU](https://cloud.google.com/run/docs/configuring/services/cpu#startup-boost) during instance startup time. To update, set [configuration](https://gitlab-com.gitlab.io/gl-infra/platform/runway/runwayctl/manifest.schema.html#spec_resources_startup_cpu_boost) in `runway.yml` of source project.

**Recommendation**: Use this setting if you need to reduce cold start latency for a service.

### Capacity Planning

Runway provides [capacity planning](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/capacity-planning/) for saturation resources of a service. To view forecasts, refer to [Tamland page](https://gitlab-com.gitlab.io/gl-infra/tamland/runway.html).

## Availability

Runway is a platform that depends on GitLab.com and GCP, so deployments cannot occur when components are unavailable.

### Regions

Runway is a platform, so services determine region availability. Runway supports multi-region deployments across 40 GCP [regions](https://gitlab-com.gitlab.io/gl-infra/platform/runway/runwayctl/manifest.schema.html#spec_regions). The default region is `us-east1`. For more information, refer to [documentation](https://docs.runway.gitlab.com/guides/multi-region/).

### Quotas

Runway is a platform, so services could be impacted by [Cloud Run quota limits](https://cloud.google.com/run/quotas#cloud_run_limits). To request quota increase, refer to [GCP console](https://console.cloud.google.com/iam-admin/quotas/qirs?service=run.googleapis.com&project=gitlab-runway-production).

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

Runway is a platform, so services determine reliability. [Cloud Run metrics](https://cloud.google.com/monitoring/api/metrics_gcp#gcp-run) are made available to services by scrapping with [Stackdriver exporter](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/runway-exporter).

When investigating issues with a service deployed to Runway, you may need to drill-down on behalf of service owner:

* [Runway Service Metrics](https://dashboards.gitlab.net/d/runway-service/runway3a-runway-service-metrics?orgId=1)
* [Runway Service Logs](https://cloudlogging.app.goo.gl/7thqEBU2EWrimDZX7)
* [Runway Service Errors](https://console.cloud.google.com/errors?project=gitlab-runway-production)
* [Runway Service Traces](https://console.cloud.google.com/traces/overview?project=gitlab-runway-production)

## Troubleshooting

### How do I rollback?

To rollback a deployment for Runway service, you have two options:

1. Revert MR, or
1. Re-run previous deployment job ([Example](https://gitlab.com/gitlab-com/gl-infra/platform/runway/deployments/ai-gateway/-/pipelines?page=1&scope=finished&status=success))

### How do I promote to production?

By default, Runway automatically promotes to production after delay of 10 minutes. To promote sooner, you can manually play `production Promote` job.

### How do I rotate secret?

Runway secrets are stored in Vault and integrated with [Secret Manager](https://cloud.google.com/run/docs/configuring/services/secrets). To rotate a secret, refer to [documentation](https://gitlab.com/gitlab-com/gl-infra/platform/runway/docs/-/blob/master/secrets-management.md?ref_type=heads#rotating-a-secret).

## Links to Infrastructure and Tooling

* [Runway Deployments](https://gitlab.com/gitlab-com/gl-infra/platform/runway/deployments)
* [Runway Services](https://console.cloud.google.com/run?project=gitlab-runway-production)
* [Runway Artifacts](https://console.cloud.google.com/artifacts?project=gitlab-runway-production)
* [Runway Application Load Balancers](https://console.cloud.google.com/net-services/loadbalancing/list/loadBalancers?project=gitlab-runway-production)
* [Runway Secrets (GSM)](https://console.cloud.google.com/security/secret-manager?project=gitlab-runway-production)
* [Runway Secrets (Vault)](https://vault.gitlab.net/ui/vault/secrets/runway/kv/list/env/production/service/)
* [Runway Provisioner](https://gitlab.com/gitlab-com/gl-infra/platform/runway/provisioner)
* [Runway Reconciler](https://gitlab.com/gitlab-com/gl-infra/platform/runway/runwayctl)
* [Runway CI Tasks](https://gitlab.com/gitlab-com/gl-infra/platform/runway/ci-tasks)
* [Runway GCP Projects](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments/runway-production)

## Links to further Documentation

* [Runway Proposal Blueprint](https://docs.gitlab.com/ee/architecture/blueprints/gitlab_ml_experiments/)
* [Runway Architecture Blueprint](https://docs.gitlab.com/ee/architecture/blueprints/runway/)
* [Runway Docs](https://gitlab.com/gitlab-com/gl-infra/platform/runway/docs)
