<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Siphon Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22siphon%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Siphon"


<!-- END_MARKER -->

## Summary

[Siphon](https://gitlab.com/gitlab-com/gl-infra/siphon) is a high-throughput data replication tool that captures changes from PostgreSQL via logical replication (CDC - change data capture) and replicates them to other data stores. The primary target is ClickHouse.

## Architecture

Siphon has two independent components communicating via NATS JetStream:

* **Producer**: Connects to PostgreSQL, reads the WAL stream via a logical replication slot, buffers events in memory, and publishes them to a NATS stream.
* **Consumer**: Subscribes to the NATS stream and writes events to the target store (e.g. ClickHouse).

Initial snapshots are handled separately: existing rows are extracted in a `REPEATABLE READ` transaction and sent to a snapshot NATS stream, which is then merged into the main stream before CDC resumes.

## Deployments

| Environment | GCP Project | Status |
| --- | --- | --- |
| Staging | `orbit-stg` | Live |
| Production | `orbit-prd` | Rollout in progress |


## Escalation Path

Primary contact: `#g_analytics_platform_insights` Slack channel ([team handbook](https://handbook.gitlab.com/handbook/engineering/data-engineering/analytics/platform-insights/)).

Individuals with the most context: `@ahegyi`, `@arun.sori` and `@ankitbhatnagar`

For immediate emergencies or if there is no response from the primary contacts, escalate to `#database_operations`.

## Monitoring

Siphon metrics are available in the [Siphon Grafana folder](https://dashboards.gitlab.net/dashboards/f/cfj21k0em8cn4c/siphon) (sandbox dashboards, select the `prd` env).

Key signal for debugging: **logical replication lag**. An increasing lag indicates the producer is falling behind or has stopped consuming from the WAL. This can have serious effect on the database health if not mitigated in a timely manner (<1 day)

Kibana logs:

* Staging: [nonprod-log.gitlab.net](https://nonprod-log.gitlab.net/app/r/s/qLnJb)
* Production: [log.gprd.gitlab.net](https://log.gprd.gitlab.net/app/r/s/6LMBY)

### PostgreSQL Replication lag

On the Siphon Producers Grafana dashboard [Siphon Grafana folder](https://dashboards.gitlab.net/dashboards/f/cfj21k0em8cn4c/siphon) the lag on the logical replication slot is tracked. The chart lists multiple slots because the slot sync (setting name: `sync_replication_slots`) feature is enabled. Slot data is periodically synchronized to replicas which ensures that when the primary is down, the slot will survive.

When determining the actual replication lag, you must look at the series that belongs to the primary (prefixed with `PRIMARY`).

When the replicas synchronize the slot from the primary, intermittently high logical replication lag might be visible on the replica nodes. This may happen when a long vacuum or transaction is running on the primary, there is nothing to do in this case, the issue will resolve itself automatically.

### Kubectl Setup

Both `orbit-stg` and `orbit-prd` environments are available via `glsh` wrapper in runbooks. It is possible to access `orbit-stg` and `orbit-prd` clusters via following the steps in the [k8s oncall setup](https://runbooks.gitlab.com/kube/k8s-oncall-setup/#summary).

```shell
glsh kube use-cluster orbit-prd --no-proxy
```

To inspect, stop, or get logs from pods, use `kubectl`:

```shell
kubectl get pods -A -o wide
```

**Important pods**

|pod name|description|
|-|-|
|`postgres-producer-$DB_NAME*`|Siphon producer process consuming the logical replication stream|
|`clickhouse-consumer-*`|Siphon consumer process ingesting data into ClickHouse|

The `$DB_NAME` indicates which database the producer connects to. Siphon always connects to the primary for logical replication. The initial data snapshot (one-time process) usually involves the DB archive node (except on Staging where snapshot is running from a replica node), which is not part of the Patroni cluster.

## Failure Modes

### High logical replication lag / producer not running

**Detection:** An automated alert monitors the Siphon producer process. If the process does not report progress, an alert is triggered. Additionally, logical replication lag metrics; WAL retention metrics on PostgreSQL might be triggered.

The slot name encodes the affected DB and environment, e.g. `stg_main_siphon_slot_1`, `prd_ci_siphon_slot_1`.

**Risk:** An inactive replication slot causes PostgreSQL to retain WAL indefinitely. If lag grows without bound, WAL accumulation will eventually exhaust disk on the PostgreSQL host. Dropping the replication slot is the last resort. Only do this when disk exhaustion is imminent. Siphon will recreate the slot on next start, but a full re-snapshot will be required.

**Steps:**

1. **Determine which DB is affected**: check the producer dashboard for the application name, which contains the DB name: `main`, `ci`, or `sec`.
1. **Check if NATS is up and running.** If the NATS service is down, Siphon is down. See the [NATS runbook](../nats/README.md).
1. **Stop Siphon** by scaling down the relevant producer deployment (adjust `postgres-producer` to the affected instance: `main`, `ci`, or `sec`):

   ```shell
   kubectl scale deployment postgres-producer --replicas=0 -n siphon
   ```

   Alternatively, prevent reconnection by disabling the database role (this is only needed when `kubectl` is not set up or extra permission is needed for accessing the `orbit` cluster):

   ```sql
   ALTER ROLE siphon_replicator NOLOGIN;
   ```

1. **Disconnect any active session** still holding the replication slot. The slot will contain the `siphon` substring. Find the PID:

   ```sql
   SELECT
     slot_name,
     active_pid,
     pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) AS lag_bytes
   FROM pg_replication_slots
   WHERE
   slot_type = 'logical' AND slot_name ILIKE '%siphon%';
   ```

   Then terminate the `active_pid` if present:

   ```sql
   SELECT pg_terminate_backend(<active_pid>);
   ```

1. **Drop the replication slot** (last resort, breaks consistency and requires re-snapshot):

   ```sql
   SELECT pg_drop_replication_slot('stg_main_siphon_slot_1');
   ```

   Siphon has a built-in retry mechanism and will recreate the slot on next startup.
