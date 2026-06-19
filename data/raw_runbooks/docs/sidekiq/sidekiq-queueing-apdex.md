# `sidekiq_queueing` apdex violation

- [Queue Detail Dashboard](https://dashboards.gitlab.net/d/sidekiq-queue-detail/sidekiq3a-queue-detail?orgId=1)
- [Shard Detail Dashboard](https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq3a-shard-detail?orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-shard=catchall&from=now-6h&to=now&timezone=utc)

## Summary

This alert is triggered when jobs are being picked up by a
Sidekiq-worker later than [the target set based on the urgency of a
worker](https://docs.gitlab.com/development/sidekiq/worker_attributes/#job-urgency).

1. `high`-urgency workloads need to start execution 5s after scheduling
1. `low`-urgency workloads need to start execution 5m after scheduling

An alert will fire if more than 0.1% of jobs don't start within their
set target.

## Debugging

1. Check inflight workers for a specific shard: <https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq3a-shard-detail?orgId=1&viewPanel=11>
   - A specific worker might be running a large amount of jobs.
1. Check apdex attribution per worker: <https://dashboards.gitlab.net/d/sidekiq-main/sidekiq3a-overview?orgId=1&from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-shard=catchall&viewPanel=panel-110>
   - If several workers are affected, it's usually a symptom of pgbouncer connection pool saturation, or other database resources.
     Check the [connection saturation per worker graph](https://dashboards.gitlab.net/d/pgbouncer-main/pgbouncer3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&viewPanel=panel-57) to see if any worker is predominantly holding connections in extended period.
   - If only a single worker is affected, the worker itself might be throttled by [concurrency limit](https://docs.gitlab.com/development/sidekiq/#concurrency-limit).
     Throttled jobs will spend queueing time in a separate concurrency limit queue, thus affecting the shard's queue apdex.
     Check <https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/sidekiq/sidekiq-concurrency-limit.md> for more info.
1. Check started jobs for a specific queue: <https://log.gprd.gitlab.net/app/r/s/v28cQ>
   - A specific worker might be enqueueing a lot of jobs.
1. Latency of job duration: <https://log.gprd.gitlab.net/app/r/s/oZnYz>
   - We might be finishing jobs slower, so we get queue build up.
1. Throughput: <https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq3a-shard-detail?orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-shard=catchall&viewPanel=panel-17&from=now-6h/m&to=now/m&timezone=utc>
   - If there is a sharp drop of a specific worker it might have slowed down.
   - If there is a sharp increase of a specific worker it's saturating the queue.

## Resolution

### Increase Capacity

You can increase the [`maxReplicas`](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/28d3a55911185087719b183cc4bbca589154bf37/releases/gitlab/values/gprd.yaml.gotmpl#L570) for the specific shard.

Things to keep in mind:

1. If we run more concurrent jobs it might add more pressure to
   downstream services (Database, Gitaly, Redis)
1. Check whether it makes sense to increase capacity, the bottleneck
   could be elsewhere, most likely a connection pool being saturated.
1. Check if this was a sudden spike or if it's sustained load.

### New Worker

It could be that this is a new worker that started running hopefully behind a feature flag that we can turn off.

### Drop worker jobs

[Drop all jobs](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/sidekiq/disabling-a-worker.md#dropping-jobs-using-feature-flags-via-chatops),
be sure that droping the jobs is safe and won't leave the application in a weird state.

### Mail queue

If the queue is all in `mailers` and is in the many tens to hundreds of thousands it is
possible we have a spam/junk issue problem. If so, refer to the abuse team for assistance,
and also <https://gitlab.com/gitlab-com/runbooks/snippets/1923045> for some spam-fighting
techniques we have used in the past to clean up. This is in a private snippet so as not
to tip our hand to the miscreants. Often shows up in our gitlab public projects but could
plausibly be in any other project as well.

### Get queues using sq.rb script

[sq](https://gitlab.com/gitlab-com/runbooks/raw/master/scripts/sidekiq/sq.rb) is a command-line tool that you can run to
assist you in viewing the state of Sidekiq and killing certain workers. To use it,
first download a copy:

```bash
curl -o /tmp/sq.rb https://gitlab.com/gitlab-com/runbooks/raw/master/scripts/sidekiq/sq.rb
```

To display a breakdown of all the workers, run:

```bash
sudo gitlab-rails runner /tmp/sq.rb
```

### Remove jobs with certain metadata from a queue (e.g. all jobs from a certain user)

We currently track metadata in sidekiq jobs, this allows us to remove
sidekiq jobs based on that metadata.

Interesting attributes to remove jobs from a queue are `root_namespace`,
`project` and `user`. The [admin Sidekiq queues
API](https://docs.gitlab.com/ee/api/admin_sidekiq_queues.html) can be
used to remove jobs from queues based on these medata values.

For instance:

```shell
curl --request DELETE --header "Private-Token: $GITLAB_API_TOKEN_ADMIN" https://gitlab.com/api/v4/admin/sidekiq/queues/post_receive?user=reprazent&project=gitlab-org/gitlab
```

Will delete all jobs from `post_receive` triggered by a user with
username `reprazent` for the project `gitlab-org/gitlab`.

Check the output of each call:

1. It will report how many jobs were deleted. 0 may mean your conditions (queue, user, project etc) do not match anything.
1. This API endpoint is bound by the HTTP request time limit, so it will delete as many jobs as it can before terminating. If the `completed` key in the response is `false`, then the whole queue was not processed, so we can try again with the same command to remove further jobs.
