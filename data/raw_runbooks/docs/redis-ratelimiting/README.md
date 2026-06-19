<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Redis-ratelimiting Service

* [Service Overview](https://dashboards.gitlab.net/d/redis-ratelimiting-main/redis-ratelimiting-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22redis-ratelimiting%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RedisRateLimiting"

## Logging

* [system](https://log.gprd.gitlab.net/goto/b0f9e5bad8ac43431efaf9f350e3a975)

## Troubleshooting Pointers

* [Ad hoc observability tools on Kubernetes nodes](../kube/k8s-adhoc-observability.md)
* [Redis on Kubernetes](../redis/kubernetes.md)
* [A survival guide for SREs to working with Redis at GitLab](../redis/redis-survival-guide-for-sres.md)
* [../redis/redis.md](../redis/redis.md)
<!-- END_MARKER -->

## Summary

**This service is decommissioned in favour of [Redis-cluster-ratelimiting Service](../redis-cluster-ratelimiting/README.md)**

The Ratelimiting Redis instances is a distinct Redis cluster used by RackAttack and Application Rate Limiting
to store the transient rate-limiting counts (almost exclusively a one minute period).  Data has a very short applicable lifespan;
the relevant period is actually stored as part of the keyname (`epoch_time / period`), and it uses Redis TTLs to
manage the data/expiry (no client activity required; old data just ages out)

It is _not_ a service to implement rate-limiting on Redis itself.

This was split because as found in <https://gitlab.com/gitlab-com/gl-infra/production/-/issues/3034#note_460538394> RackAttack
alone accounted for somewhere in the order of 25% (absolute) CPU usage on the redis-cache instance in Nov 2020, and that will
only have grown with traffic.

As the cache cluster approached 95% saturation it was determined the best short-term approach was to split out the rate-limiting
data storage to its own cluster before we go further with more horizontal scalability.

## Architecture

Redis is in the usual 3-node single-primary/two-replica VM configuration, with sentinels on the same VMs as Redis (as for persistent and sidekiq clusters)

<!-- ## Performance -->

## Scalability

Single threaded CPU is the normal constraint for Redis, and will in particular be the case here.  It is CPU heavy, and _not_ data
heavy.  Analysis suggests data volumes are in the order of MBs, not GBs, and small numbers at that.

## Availability

The usual redis availability expectations for our 3-node clusters apply (see <https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/redis/redis-survival-guide-for-sres.md#high-availability> )

## Durability

Unimportant; data has a (almost exclusively) 1 minute useful period.  If we lost all data in this cluster, within 1 minute (at most) all effects would be passed, and at worst during that 1 minute some users might be able to access the system at up to double the usual rate-limit (an absolute upper limit, depending on which part of the minute the failure happened and the distribution of their requests during that period).

<!-- ## Security/Compliance -->

## Monitoring/Alerting

Uses the same metrics-catalog definitions as for the other Redis clusters.

## Links to further Documentation

* Implementation/migration epic: <https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/526>
