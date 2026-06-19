<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Grafana Mimir Service

* [Service Overview](https://dashboards.gitlab.net/d/mimir-main/mimir3a-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22mimir%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Mimir"

## Logging

* [Elasticsearch](https://nonprod-log.gitlab.net/app/r/s/BLV6G)

<!-- END_MARKER -->

<!-- ## Summary -->
## Quick Links

| Reference | Link |
| --- | --- |
| Helm Deployment | [ArgoCD](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/mimir) |
| Tenant Configuration | [config-mgmt](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments/observability-tenants) |
| Runbooks | [Grafana Runbooks](https://grafana.com/docs/mimir/latest/manage/mimir-runbooks/) |
| Dashboards | [Mimir Overview](https://dashboards.gitlab.net/d/ffcd83628d7d4b5a03d1cafd159e6c9c/mimir-overview?orgId=1) |
| Logs | [Elastic Cloud](https://nonprod-log.gitlab.net/app/r/s/h3UsR) |

## Troubleshooting

If you received a page for Mimir, the first thing is to determine if the problem is on the write path, read path, or with recording rule evaluation.

As well as checking if the problem is isolated to a single tenant, or effecting all tenants.

We have some useful dashboards to reference for a quick view of system health:

* [Overview](https://dashboards.gitlab.net/d/ffcd83628d7d4b5a03d1cafd159e6c9c/mimir-overview?orgId=1)
* [Writes](https://dashboards.gitlab.net/d/8280707b8f16e7b87b840fc1cc92d4c5/mimir-writes?orgId=1)
* [Reads](https://dashboards.gitlab.net/d/e327503188913dc38ad571c647eef643/mimir-reads?orgId=1)
* [Rule Evaluations](https://dashboards.gitlab.net/d/631e15d5d85afb2ca8e35d62984eeaa0/mimir-ruler?orgId=1)
* [Mimir Tenants](https://dashboards.gitlab.net/d/35fa247ce651ba189debf33d7ae41611/mimir-tenants?orgId=1)

There are other useful operational dashboards you can navigate to from the top right, under "Mimir dashboards".

When checking tenants, the key metrics/questions here are:

* Is the tenant exceeding a quota?
  * To increase quotas, see the [getting-started](./getting-started.md) docs.
* Is the "Newest seen sample age" recent.
  * If there is no recent samples coming in, this could indicate the remote-write client may be experiencing issues and not sending any data.
* Are any series being dropped under "Distributor and ingester discarded samples rate".
  * Dropped samples would usually be the effect of a quota being exceeded so refer to the quota point above.

It's also worth checking the observability alerts channel on slack `#g_infra_observability_alerts`,
as there is some much more targeted alerting that will have direct links to appropriate [runbooks](#runbooks).

## Runbooks

We use a slightly refactored version of the [Grafana Monitoring Mixin](https://gitlab.com/gitlab-com/gl-infra/monitoring-mixins) for much of the operational monitoring.

As such the Grafana Runbooks apply to our alerts as well, and are the best source of information for troubleshooting:

* [Grafana Runbooks](https://grafana.com/docs/mimir/latest/manage/mimir-runbooks/)
* [Grafana Dashboards](https://dashboards.gitlab.net/d/ffcd83628d7d4b5a03d1cafd159e6c9c/mimir-overview?orgId=1)

## Onboarding

See the [getting-started readme](./getting-started.md)

## Cardinality Management

Metrics cardinality is the silent performance killer in Prometheus.

Start with the [cardinality-management readme](./cardinality-management.md) to help identify problem metrics.

<!-- ## Architecture -->

## Architecture

[Architecture Reference](https://grafana.com/docs/mimir/latest/references/architecture/).

We deploy in the [microservices mode](https://grafana.com/docs/mimir/latest/references/architecture/deployment-modes/#microservices-mode) via [ArgoCD](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/mimir?ref_type=heads).

There are [additional GCP components](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/866f554c5c18f01c36deeb28cdd51de8caee2b51/services/mimir/values.yaml#L629) deployed via the helm chart using [config-connector](https://cloud.google.com/config-connector/docs/overview).

This includes storage buckets and IAM policies. These componets are deployed to the `gitlab-observability` GCP project, as this keeps the config connector permissions scoped and blast radius limited to the observability services.

![mimir-architecture](img/mimir-architecture-overview.png)

<!-- ## Performance -->

<!-- ## Scalability -->

## Capacity Planning

There is some good capacity planning docs from Grafana [here](https://grafana.com/docs/mimir/latest/manage/run-production-environment/planning-capacity/#microservices-mode).

These include some guidelines around sizing for various components in Mimir.

Keep in mind that at GitLab we have some incredibly high cardinality metrics, and while these numbers serve as good guidelines we often require more resources than recommended.

## Scaling Mimir

### Scaling up

All components in Mimir are horizontally scalable.

We have autoscaling in place for the following components:

* Distributor
* Querier
* Query-Frontend

All components can be scaled up without concern.

The main consideration with scaling up is that with [shuffle sharding](https://grafana.com/docs/mimir/latest/configure/configure-shuffle-sharding/) enabled, new pods might not pick up workloads depending on shard assignments.

There is a [runbook](https://grafana.com/docs/mimir/latest/manage/mimir-runbooks/#mimiringesterinstancehasnotenants) for the various component explaining the cause and fix in more detail.

### Scaling down

Scaling down for stateless components can be done without issue, with only the usual concerns for saturation and ensuring enough resource is left available.

There are several stateful components in Mimir that require special consideration when scaling down.

* Alertmanagers
* Ingesters
* Store-Gateways

Scaling down these needs to be done following a process as they contain recent data used for querying, unexpected removal of this data can cause missing datapoints.

More details on scaling down these components can be [read here](https://grafana.com/docs/mimir/latest/manage/run-production-environment/scaling-out/#microservices-mode)

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

<!-- ## Links to further Documentation -->
