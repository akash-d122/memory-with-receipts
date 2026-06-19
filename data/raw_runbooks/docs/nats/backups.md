# NATS Backup

We run NATS on Kubernetes via its Helm chart which is based on Stateful sets.

We use [velero](https://velero.io/docs/v1.9/how-velero-works/) to backup the complete NATS workload and persist them to remote storage. It also takes snapshots of associated volumes.
Backed up resources include:

* NATS StatefulSet configurations
* Persistent volumes containing NATS data
* Associated Kubernetes resources (ConfigMaps, Secrets, Services)

* This is rolled out on all customersdot environments. See [gitlab-org/analytics-section/platform-insights/core#83](https://gitlab.com/gitlab-org/analytics-section/platform-insights/core/-/issues/83).

## Backup Schedule and Retention

For staging environments, the frequency is of daily backups with retention period of 3 days.
For production environment, the frequency is every 6 hours with retention period of 3 days.

| Environment | Frequency | Retention Period | Schedule Expression |
|-------------|-----------|------------------|---------------------|
| Staging     | Daily     | 3 days          | `0 2 * * *`         |
| Production  | Every 6 hours | 3 days      | `0 */6 * * *`       |

## Prerequisites

Before troubleshooting or performing restore operations:

1. Make sure to configure `kubectl config context` properly to point to the cluster.

    ```shell
    # Verify cluster access
    $ kubectl config current-context

    # Switch to the correct cluster if needed
    $ kubectl config use-context <cluster-name>
    ```

2. Velero CLI (optional but recommended)

    * [Installation guide](https://velero.io/docs/v1.16/basic-install/)
    * With the CLI installed, you can omit kubectl exec commands, example: `velero backup get` instead of `kubectl exec -n velero deployment/velero -- /velero backup get`

3. Required permissions:

   * Read access to the velero and nats namespaces
   * For restore operations: write access to the nats namespace

## Troubleshooting

### Monitoring and Alerts

#### Alert Configuration

We have an [alert defined](../../mimir-rules/fulfillment-platform/nats/velero-backups.yml) that triggers when there are no successful backups in last 12 hours.

#### Key Metrics

There are several metrics available on [Grafana](https://dashboards.gitlab.net/) that can be used to monitor the backups:

| Metric | Description | Link                                                              |
|--------|-------------|-------------------------------------------------------------------|
| `velero_backup_last_successful_timestamp` | Timestamp of last successful backup | [View](https://dashboards.gitlab.net/goto/ef4l3ux1ht7ggc?orgId=1) |
| `velero_backup_failure_total` | Total number of failed backups | [View](https://dashboards.gitlab.net/goto/ff4laxrc48em8b?orgId=1) |
| `velero_backup_attempt_total` | Total backup attempts | [View](https://dashboards.gitlab.net/goto/cf4lazobh8j5se?orgId=1) |

Failure rate [query](https://dashboards.gitlab.net/goto/cf4l48uz5sfswe?orgId=1):

```promql
sum(rate(velero_backup_failure_total{env="gprd"}[12h])) /
sum(rate(velero_backup_attempt_total{env="gprd"}[12h])) * 100
```

The backups can also be investigated directly on the kubernetes cluster.

### Checking active velero schedule

```shell
$ kubectl exec -n velero deployment/velero -- /velero schedule get # or `velero schedule get`
NAME                 STATUS    CREATED                         SCHEDULE      BACKUP TTL   LAST BACKUP   SELECTOR   PAUSED
velero-nats-backup   Enabled   2025-10-27 17:02:51 +0000 UTC   0 */6 * * *   72h0m0s      5h ago        <none>     false
```

### Checking failed backups

```shell
$ kubectl exec -n velero deployment/velero -- /velero backup get # or `velero backup get`
NAME                                STATUS      ERRORS   WARNINGS   CREATED                         EXPIRES   STORAGE LOCATION   SELECTOR
...
velero-nats-backup-20251117060039   Completed   0        0          2025-11-17 07:00:39 +0100 CET   19h       default            <none>
velero-nats-backup-20251117000039   Completed   0        0          2025-11-17 01:00:39 +0100 CET   13h       default            <none>
velero-nats-backup-20251116180038   Completed   0        0          2025-11-16 19:00:38 +0100 CET   7h        default            <none>
velero-nats-backup-20251116120038   Completed   0        0          2025-11-16 13:00:38 +0100 CET   1h        default            <none>
```

Failed backups would have the status as `Failed`. We can peek into a backup for more details.

```shell
$ kubectl exec -n velero deployment/velero -- /velero backup describe velero-nats-backup-20251116120038
# output has been elided as it includes lot more details but the important things to look are `Phase`, `Started/Completed` and `Item backed up` and it will include errors
Name:         velero-nats-backup-20251116120038
Namespace:    velero
...
Phase:  Completed
Namespaces:
  Included:  nats
  Excluded:  <none>
Resources:
  Included:        *
  Excluded:        <none>
  Cluster-scoped:  included
...
TTL:  72h0m0s
...
Started:    2025-11-16 12:00:38 +0000 UTC
Completed:  2025-11-16 12:01:03 +0000 UTC

Expiration:  2025-11-19 12:00:38 +0000 UTC

Total items to be backed up:  709
Items backed up:              709
```

In order to look into why a particular failure happened, backups logs can be helpful, though it is quite verbose:

```shell
$ kubectl exec -n velero deployment/velero -- /velero backup logs velero-nats-backup-20251116120038
```

Velero [documentation](https://velero.io/docs/v1.16/troubleshooting/#general-troubleshooting-information) also includes a general troubleshooting section.

### Manually triggering a backup

It is also possible to trigger a manual backup instead of waiting on the schedule or to actively monitor if there are errors:

```shell
$ kubectl exec -n velero deployment/velero -- /velero backup create nats-{timestamp} --include-namespaces nats --wait
```

This will create a backup that will include all resources in the namespace `nats`.

## Restore procedure

Backups made by `velero` can be restored by using the [Restore API](https://velero.io/docs/v1.17/api-types/restore/) available.

An example resource to execute a restore looks like this:

```yaml
apiVersion: velero.io/v1
kind: Restore
metadata:
  name: nats-restore
  namespace: velero
  labels:
    restore-type: disaster-recovery
spec:
  scheduleName: velero-nats-backup
  ## or modify this to point to specific backup created by velero
  # backupName: nats-30-10-2025

  includedNamespaces:
  - nats

  # Restore persistent volumes
  restorePVs: true

  preserveNodePorts: true

  includeClusterResources: true

  includedResources:
  - '*'
 ```

This resource can be applied to the cluster and it will restore all NATS kubernetes resources onto cluster.

For more details on the workflow and available configuration, see `velero` [restore reference doc](https://velero.io/docs/v1.17/restore-reference/).
