# KubeServiceClusterScaleupsErrorSLOViolation

## Overview

This alert fires when the GKE [Cluster Autoscaler](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler) fails to scale up node pools at a rate that violates our SLO.

The `cluster_scaleups` SLI for the `kube` service treats each scale-up decision by the Cluster Autoscaler as an operation and each scale-up failure as an error. The alert fires when the error ratio exceeds `14.4 × 5%` (~72%) over both a 1h and 5m window, with at least 1 op/s of scale-up activity, sustained for 2 minutes.

What this means in practice:

- Pending pods are unable to acquire new nodes.
- Workloads that depend on horizontal scaling (HPA-driven and otherwise) may stall, leading to saturation or deployment failures downstream.
- The alert is labelled `user_impacting: "no"` and severity `s2`, but it is frequently a precursor to user-impacting saturation alerts (for example `KubeContainersWaitingInError`).

The recipient of this alert should:

1. Identify which cluster(s) and node pool(s) are failing to scale.
2. Determine the underlying cause (quota, stockout, IP exhaustion, max-nodes cap, etc.).
3. Take corrective action or escalate if it cannot be self-resolved.

## Services

- [kube Service Overview](../kubernetes.md)
- Owner: `fleet_management`

## Metrics

The SLI is defined in [`metrics-catalog/services/kube.jsonnet`](../../../metrics-catalog/services/kube.jsonnet) under the `cluster_scaleups` component, and is built from two Stackdriver log-based metrics exported from the GKE Cluster Autoscaler visibility logs:

- `stackdriver_k_8_s_cluster_logging_googleapis_com_user_k_8_s_cluster_autoscaler_scaleup_decisions` — operations (each scale-up attempt)
- `stackdriver_k_8_s_cluster_logging_googleapis_com_user_k_8_s_cluster_autoscaler_scaleup_errors` — errors (each scale-up failure)

Threshold rationale:

- The error budget is `monitoringThresholds.errorRatio: 0.95` (i.e. we tolerate up to 5% scale-up errors).
- The alert uses a multi-window burn-rate of `14.4 × 0.05` over both 1h and 5m windows, which is the standard fast-burn pattern for a 30-day SLO.
- The minimum-traffic gate (`>= 1 op/s`) prevents the alert from firing during periods with no autoscaler activity (log-based metrics gap-fill with zero).

Expected normal behavior:

- The Cluster Autoscaler runs scale-up evaluations roughly every 10 seconds.
- Transient scale-up failures (for example a single zone stockout that resolves on retry) are expected at low rates and absorbed by the error budget.
- Sustained high error ratios indicate a structural problem (quota, IP exhaustion, max-nodes cap, IAM regression).

Dashboards:

- [`kube-overview`](https://dashboards.gitlab.net/d/kube-main/kube-overview) — filter by `environment` and `stage` from the alert labels.
- TODO: capture screenshot of the `kube-overview` panel during a real firing of this alert. Future firings should attach examples to the [label-filtered production issues](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=a%3AKubeServiceClusterScaleupsErrorSLOViolation) so this section can be updated.

## Alert Behavior

- The alert is paged via Incident.io at severity `s2`.
- It should be rare. Sustained firing usually indicates a real, structural cluster problem rather than a transient blip.
- Avoid broad silences. If a silence is needed (e.g. a known terraform change is in flight), scope it to the smallest viable set of labels — typically `stage`, `environment`, and `cluster_name`.
- Because the underlying metrics are Stackdriver log-based and gap-fill with zero, a brief firing followed by quick recovery can indicate a one-off zonal stockout or quota blip. Repeat firings within a short window are the more important signal.

## Incident Severities

- Default Incident Severity: **s3**.
- Consider escalating to **s2** if any of the following are true:
  - A user-impacting workload (`web`, `api`, `sidekiq`, `gitaly`) is unable to schedule new pods due to the failure.
  - This alert is firing alongside `KubeContainersWaitingInError`, `GKENodeCountCritical`, or other saturation alerts on the same cluster.
  - The root cause is a GCP quota or capacity issue that cannot be self-resolved within the on-call shift.
- Impact assessment:
  - Internal-only: scale-up failures on infrastructure node pools that are not on the customer hot path.
  - Customer-facing: scale-up failures on node pools backing `web`, `api`, `sidekiq`, or `gitaly` workloads when load is rising.

## Verification

Confirm the alert reflects a real, ongoing problem before deep diagnosis:

1. Open the [`kube-overview` dashboard](https://dashboards.gitlab.net/d/kube-main/kube-overview) (link is also in the alert annotation) filtered to the firing `environment` and `stage`.
2. Confirm the SLI ratio is elevated:

    ```promql
    gitlab_component_errors:ratio_5m{component="cluster_scaleups",env="gprd",type="kube"}
    ```

3. Break down errors by cluster to identify which cluster(s) are affected:

    ```promql
    sum by (cluster_name) (
      avg_over_time(stackdriver_k_8_s_cluster_logging_googleapis_com_user_k_8_s_cluster_autoscaler_scaleup_errors[5m])
    )
    ```

    Example output during a firing:

    ```
    {cluster_name="gprd-us-east1-b"}  0.83
    {cluster_name="gprd-us-east1-c"}  0
    {cluster_name="gprd-us-east1-d"}  0
    ```

    A non-zero value for one cluster and zero for the others indicates the problem is localized to that cluster (and usually to a specific node pool within it).

4. Cross-check from the cluster itself by inspecting the autoscaler status ConfigMap (see Troubleshooting). If the SLI shows errors but the ConfigMap shows everything healthy, suspect a metric pipeline lag (Stackdriver → Mimir) rather than a real fault.

Stackdriver log links for raw error details are wired into the metrics catalog as tooling links and are surfaced from Grafana and the alert details:

- [Kubernetes Autoscaler Logs](https://cloud.google.com/logging/docs)
- [Kubernetes Autoscaler Errors](https://cloud.google.com/logging/docs) (filtered on `jsonPayload.resultInfo.results.errorMsg.messageId`)

## Recent changes

- [Recent related production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=change%3A%3Acomplete)
- [Recent `config-mgmt` MRs](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests?sort=merged_at_desc&state=merged) — node pool sizes, max-nodes caps, instance types, zones, IAM, and quotas are managed here.
- [Recent ArgoCD MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests/?sort=merged_at_desc&state=merged) and [recent `k8s-workloads` MRs](https://gitlab.com/groups/gitlab-com/gl-infra/k8s-workloads/-/merge_requests?sort=merged_at_desc&state=merged) — workloads with new resource requests, affinities, or tolerations can leave pods unschedulable, which can in turn surface as scale-up failures.
- To roll back a change, find the MR that introduced it (typically in `config-mgmt` for node pool / quota changes, or ArgoCD or `k8s-workloads` for workload changes) and revert it. Confirm the pipeline completes.

## Troubleshooting

Recommended order of investigation:

1. Identify the firing cluster(s) and stage from the alert labels and the per-cluster PromQL in the Verification section.
2. Connect to the cluster:

    ```bash
    glsh kube use-cluster <env>
    ```

> [!tip]
> You can get a list of clusters to connect to with the `glsh kube use-cluster` command with no environment specified.

3. Review the Cluster Autoscaler's own status snapshot:

    ```bash
    kubectl describe configmap cluster-autoscaler-status -n kube-system
    ```

    This is usually the fastest way to pinpoint the failing node pool. Look for:

    - `Health` per node group — a `Healthy: False` block names the node group and reason.
    - `ScaleUp` block — states are `InProgress`, `NoActivity`, or `Backoff`. A `Backoff` block includes the last error and the retry time.
    - Node group sizes — `cloudProviderTarget`, `minSize`, `maxSize`. A node group at `maxSize` cannot scale further; this often correlates with `GKENodeCountCritical` / `GKENodeCountHigh` (see [`kubernetes.md`](../kubernetes.md)).
    - Last transition timestamps — correlate with the alert firing time.

    The ConfigMap is updated approximately every 10 seconds and reflects live state.

4. Open the Stackdriver Cluster Autoscaler error logs (link is on the alert and on the Grafana dashboard) and read the `jsonPayload.resultInfo.results.errorMsg.messageId` field. The most common causes we have seen in production are listed in the table below.
5. Identify pending pods to understand what is being blocked:

    ```bash
    kubectl get pods -A --field-selector=status.phase=Pending
    ```

6. Look at scheduling failures:

    ```bash
    kubectl get events -A --field-selector reason=FailedScheduling
    ```

7. If a node pool is at its cap, inspect its terraform-managed limits:

    ```bash
    gcloud container node-pools describe <node-pool> \
      --project="${GOOGLE_PROJECT}" \
      --region="${GOOGLE_REGION}" \
      --cluster="${CLUSTER_NAME}"
    ```

    The authoritative max-node configuration lives in [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/).
8. Check the [GCP quotas page](https://console.cloud.google.com/iam-admin/quotas) for the project — particularly CPUs, in-use IP addresses, Hyperdisk, SSD persistent disk, and the regional/zonal quota for the relevant instance family.

### Top causes we have seen in production

| `messageId` / cause | Meaning | First-line action |
| --- | --- | --- |
| `scale.up.error.quota.exceeded` | A GCP quota was hit (CPUs, IPs, Hyperdisk, SSD, instance group size). | Cross-check the [GCP quota runbook](../../uncategorized/alerts/gcp_quota_limit.md). Request a quota increase via the project's GCP console or open a Google Cloud support case. |
| `scale.up.error.out.of.resources` | GCE stockout in the target zone for the requested instance type. | Usually transient — the autoscaler will retry. If sustained, add a new node pool with a different machine family via Terraform in [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/). |
| `scale.up.error.ip.space.exhausted` | Pod or node CIDR is exhausted for the cluster. Each node allocates a `/24` CIDR block from the pod IP range(s) and fails to provision if it cannot. | **Pod subnet exhausted**: add a secondary pod subnet in [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/) (example: [`config-mgmt!13329`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/13329)). **Cluster (node) subnet exhausted**: the cluster must be reprovisioned with a larger subnet — coordinate with networking; this is not a quick fix. |
| `scale.up.error.waiting.for.instances.timeout` | GCE instance creation timed out before the node became Ready. | Check the [GCP status page](https://status.cloud.google.com/), retry, and inspect the node pool image/startup. If recent, correlate with image version or terraform changes. |
| Max nodes reached (Terraform cap) | The node pool is at its configured maximum and the autoscaler cannot grow it. | Cross-link to [`GKENodeCountCritical` / `GKENodeCountHigh`](../kubernetes.md#gkenodecountcritical). Raise the cap in [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/) only after confirming headroom is needed. Note: `maxSize` cannot exceed the number of IPs available in the cluster subnet — if the subnet is the binding limit, see the `scale.up.error.ip.space.exhausted` row instead. |

For the full list of GKE Cluster Autoscaler `messageId` values, see the [GKE cluster autoscaler error reference](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler#messages).

## Possible Resolutions

- [Previous incidents for this alert](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=a%3AKubeServiceClusterScaleupsErrorSLOViolation)

When resolving an incident under this alert, please add a link here so future on-call engineers can learn from it.

## Dependencies

- GCP project quotas (CPUs, in-use IPs, Hyperdisk, SSD persistent disk, instance group size).
- GCE zonal capacity for the instance types used by our node pools.
- Cloud Logging ingestion — the SLI is built from log-based metrics, so a Stackdriver outage can affect the signal.
- Terraform-managed node pool definitions in [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt).
- IAM / service account configuration for the node pools.

## Escalation

- Primary: `#g_fleet_management`
- Adjacent: Delivery for workload-owner questions when a specific GitLab.com deployment is affected.
- For GCP quota or stockout issues that cannot be self-resolved within the on-call shift, open a support case with Google Cloud and link it from the incident.

## Definitions

- SLI source: [`metrics-catalog/services/kube.jsonnet`](../../../metrics-catalog/services/kube.jsonnet) under `components.cluster_scaleups`.
- Generated alert rules: `mimir-rules/gitlab-{gprd,gstg,pre,ops}/kube/autogenerated-*-kube-service-level-alerts.yml`.
- The only tunable parameter is `monitoringThresholds.errorRatio` on the SLI. Raising it widens the error budget; do this only if there is a justified, persistent operational reason and a corresponding plan to address the underlying cause.
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/kube/alerts/KubeServiceClusterScaleupsErrorSLOViolation.md?ref_type=heads)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md?ref_type=heads)

## Related Links

- [Related alerts](./)
- [`kubernetes.md`](../kubernetes.md) — `GKENodeCountCritical`, `GKENodeCountHigh`
- [`KubeContainersWaitingInError`](./KubeContainersWaitingInError.md)
- [GCP quota limit runbook](../../uncategorized/alerts/gcp_quota_limit.md)
- [GKE Cluster Autoscaler concepts](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler)
