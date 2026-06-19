# Sidekiq Concurrency Limit

## Throttling/Circuit Breaker based on database usage

To protect the primary database against misbehaving/inefficient workers which can lead into incidents like
slowdown of jobs processing, web availability, etc, we have developed a circuit breaking mechanism
within Sidekiq itself.

When the database usage of a worker [violates an indicator](#database-usage-indicators), Sidekiq will throttle the worker by decreasing its concurrency limit
at an interval of every minute. In the worst case scenario, the worker's concurrency limit will be suppressed down to `1`.

Once the database usage has gone to a healthy level, the concurrency limit will automatically recover towards its default limit, but at a much slower rate than the throttling rate. The definition of the throttling/recovery rate is defined [here](https://gitlab.com/gitlab-org/gitlab/blob/ae8a9687d65573f2945863fda97f144381f2a782/lib/gitlab/sidekiq_middleware/throttling/strategy.rb#L9-12).

Observability around concurrency limit can be viewed at [sidekiq: Worker Concurrency Detail dashboard](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq3a-worker-concurency-detail?from=now-24h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1).

> [!note]
> Since throttled jobs will spend its queueing time in a separate concurrency limit queue, the apdex of `sidekiq_queueing` SLI for the respective
> shard could be affected too if there are a lot of jobs for this worker being throttled.
> Only jobs for this worker class will however be affected, other jobs will start normally.

### Database usage indicators

There are 2 indicators on which the application will throttle a worker:

1. DB duration usage (primary DBs only)

   **Dashboard:**

   - [Main DB duration](https://log.gprd.gitlab.net/app/r/s/mvUdr)
   - [CI DB duration](https://log.gprd.gitlab.net/app/r/s/LcvLB)
   - [Sec DB duration](https://log.gprd.gitlab.net/app/r/s/bTMsh)

   > [!important]
   > Make sure to check all primary DBs usage, ie `json.db_main_duration_s`, `json.db_ci_duration_s` and `json.db_sec_duration_s`.
   > If any one of the DB duration limit is exceeded, throttling event will kick in.

   By default, the per-minute DB duration should not exceed a limit of
   20,000 DB seconds/minute on non-high urgency worker and
   100,000 DB seconds/minute on high-urgency workers ([source](https://gitlab.com/gitlab-org/gitlab/blob/ae8a9687d65573f2945863fda97f144381f2a782/lib/gitlab/sidekiq_limits.rb#L5-7)).

   The limits above can also be overwritten as described [below](#updating-db-duration-limits). To check the current limit:

   ```bash
   glsh application_settings get resource_usage_limits -e gprd
   ```

2. Number of non-idle DB connections

   **Dashboard**:

   - [pgbouncer connection saturation](https://dashboards.gitlab.net/d/pgbouncer-main/pgbouncer3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&viewPanel=panel-57)
   - [pgbouncer-ci connection saturation](https://dashboards.gitlab.net/d/pgbouncer-ci-main/pgbouncer-ci3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&viewPanel=panel-57)
   - [pgbouncer-sec connection saturation](https://dashboards.gitlab.net/d/pgbouncer-sec-main/pgbouncer-sec3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&viewPanel=panel-57)

   Sidekiq [periodically](https://gitlab.com/gitlab-org/gitlab/blob/d5a647efaf6930d99b5aac54d284a1780a57e6c1/lib/gitlab/metrics/samplers/stat_activity_sampler.rb#L7)
   samples non-idle DB connections from `pg_stat_activity` to determine which worker classes are consuming the most connections.

   The system determines the **predominant worker** (the worker consuming the most connections) by:

   1. [Summing the number of connections used by a worker over the last 4 samples of `pg_stat_activity`](https://gitlab.com/gitlab-org/gitlab/blob/d5a647efaf6930d99b5aac54d284a1780a57e6c1/lib/gitlab/sidekiq_middleware/throttling/decider.rb#L37-46) (approximately 4 minutes of data)
   2. The worker with the most aggregated connections is the "predominant worker"

### Throttling events

The table below illustrates what happens when each indicator is violated:

| Indicator 1 (DB duration) | Indicator 2 (DB connections) | Throttling Event                                                                                          |
| ------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------- |
| ❌                        | ✅                           | Soft Throttle                                                                                             |
| ❌                        | ❌                           | Hard Throttle                                                                                             |
| ✅                        | ❌                           | No throttling. Not throttled as some workers may momentarily hold many connections during normal workload |
| ✅                        | ✅                           | No throttling                                                                                             |

> [!note] Legends
>
> - ❌ - failed the indicator check
> - ✅ - passed the indicator check
> - Soft Throttle - worker's current limit decreased by 20% per minute
> - Hard Throttle - worker's current limit decreased by 50% per minute

### Updating DB duration limits

The DB duration usage described [above](#database-usage-indicators) can only be updated by calling the [application settings API](https://docs.gitlab.com/api/settings/#update-application-settings). It cannot currently be set using the admin web UI.

> [!important]
> The `resource_usage_limits` accepts a JSON validated by a [JSON schema](https://gitlab.com/gitlab-org/gitlab/blob/ae8a9687d65573f2945863fda97f144381f2a782/app/validators/json_schemas/resource_usage_limits.json#L1-1).

1. Prepare a JSON file. Here's an example to update a single worker `Chaos::DbSleepWorker` to have its own limit on the main DB:

   <details>
   <summary>Click to expand</summary>

   ```json
   ❯ cat rules.json
   {
     "rules": [
       {
         "name": "main_db_duration_limit_per_worker",
         "resource_key": "db_main_duration_s",
         "metadata": {
           "db_config_name": "main"
         },
         "scopes": [
           "worker_name"
         ],
         "rules": [
          {
            "selector": "worker_name=Chaos::DbSleepWorker",
            "threshold": 5,
            "interval": 60
          },
           {
             "selector": "urgency=high",
             "threshold": 100000,
             "interval": 60
           },
           {
             "selector": "*",
             "threshold": 20000,
             "interval": 60
           }
         ]
       },
       {
         "name": "ci_db_duration_limit_per_worker",
         "resource_key": "db_ci_duration_s",
         "metadata": {
           "db_config_name": "ci"
         },
         "scopes": [
           "worker_name"
         ],
         "rules": [
           {
             "selector": "urgency=high",
             "threshold": 100000,
             "interval": 60
           },
           {
             "selector": "*",
             "threshold": 20000,
             "interval": 60
           }
         ]
       },
       {
         "name": "sec_db_duration_limit_per_worker",
         "resource_key": "db_sec_duration_s",
         "metadata": {
           "db_config_name": "sec"
         },
         "scopes": [
           "worker_name"
         ],
         "rules": [
           {
             "selector": "urgency=high",
             "threshold": 100000,
             "interval": 60
           },
           {
             "selector": "*",
             "threshold": 20000,
             "interval": 60
           }
         ]
       }
     ]
   }
   ```

   </details>

   > [!note]
   > The `selector` field follows the same [worker matching query](https://docs.gitlab.com/administration/sidekiq/processing_specific_job_classes/#worker-matching-query)
   > which is used in sidekiq routing rules too.

   To prepare a file with the current configuration to edit, run:

   ```bash
   glsh application_settings get resource_usage_limits > rules.json
   ```

1. Run a helper script `glsh application_settings resource_usage_limits` to update the limits with an admin PAT.

   ```bash
   glsh application_settings set resource_usage_limits -f rules.json -e gprd
   ```

### Disabling the Throttling/Circuit Breaker feature entirely

To disable throttling globally for all workers:

```
/chatops gitlab run feature set sidekiq_throttling_middleware false
```

To disable throttling for a worker:

```
# replace Security::SecretDetection::GitlabTokenVerificationWorker with the worker you want to disable
/chatops gitlab run feature set `disable_sidekiq_throttling_middleware_Security::SecretDetection::GitlabTokenVerificationWorker` true
```

## SidekiqConcurrencyLimitQueueBacklogged Alert

This alert fires when a Sidekiq worker has accumulated too many jobs in the Concurrency Limit queue (>100,000 jobs for more than 1 hour).

The long backlog is usually caused by higher arrival rate of jobs compared to the rate of resumed jobs by `ConcurrencyLimit::ResumeWorker`.

- The arrival rate is equal to the worker deferment rate, which can be found [here](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=2025-11-13T05:30:44.178Z&to=2025-11-13T11:30:44.178Z&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=ReactiveCachingWorker&orgId=1&viewPanel=panel-4).
- The rate of resuming jobs can be found in [Kibana](https://log.gprd.gitlab.net/app/r/s/Aw54b).

If the arrival rate is consistently higher than the rate of resuming jobs, the only option is to disable the concurrency limit for the worker class as described in Option 2 below.

These jobs are queued in Redis Cluster SharedState, so large amount of jobs could saturate Redis Cluster SharedState memory if left untreated.

### Option 1: Increase Worker Concurrency Limit

If the worker can safely handle more concurrent jobs:

1. Locate the worker definition in the codebase
2. Check current concurrency limit setting from the [dashboard](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=ProcessCommitWorker&orgId=1&viewPanel=panel-7) or the worker class definition.
3. Create an MR to increase the limit to an appropriate value based on [concurrent jobs](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=ProcessCommitWorker&orgId=1&viewPanel=panel-6)

If `concurrency_limit` attribute is not set in the worker class, consider overriding
[`max_concurrency_limit_percentage` attribute](https://gitlab.com/gitlab-org/gitlab/blob/fee2b14e9d2f47bbae7638cce1c04205703e6241/app/workers/flush_counter_increments_worker.rb#L27-27) to use higher percentage of max total threads in the Sidekiq shard. The default
percentage can be found [here](https://gitlab.com/gitlab-org/gitlab/blob/fee2b14e9d2f47bbae7638cce1c04205703e6241/app/workers/concerns/worker_attributes.rb#L44-49) (based on worker's urgency).

### Option 2: Temporarily Disable Concurrency Limit

Alternatively, `disable_sidekiq_concurrency_limit_middleware_#{worker_name}` feature flag can be enabled to help clear the backlogs instantly
without waiting for deployment as in Option 1.

1. Enable the feature flag:

```
/chatops gitlab run feature set `disable_sidekiq_concurrency_limit_middleware_WebHooks::LogExecutionWorker` true --ignore-feature-flag-consistency-check
```

2. Monitor the [concurrency limit queue size](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-2282485207) to confirm it's draining
3. If we decide to increase the concurrency limit, wait until the limit has been increased and disable the feature flag back:

```
/chatops gitlab run feature delete `disable_sidekiq_concurrency_limit_middleware_WebHooks::LogExecutionWorker`
```

When the concurrency limit middleware is disabled:

- Jobs will be resumed at a higher pace.
- New jobs will execute immediately.

### Post-Incident Tasks

1. Create an issue to properly address the root cause if Option 2 was used
2. Update monitoring thresholds if needed

## Useful Dashboards

- [sidekiq: Worker Concurrency Detail](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq3a-worker-concurency-detail?from=now-24h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1)
- [Redis Cluster SharedState metrics](https://dashboards.gitlab.net/d/redis-cluster-shared-state-main/redis-cluster-shared-state3a-overview?orgId=1&from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-shard=$__all)
- [Sidekiq: Overview](https://dashboards.gitlab.net/d/sidekiq-main/sidekiq-overview)

## References

- [Concurrency limit worker attribute](https://docs.gitlab.com/development/sidekiq/worker_attributes/#concurrency-limit)
