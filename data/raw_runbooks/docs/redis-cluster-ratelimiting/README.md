<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Redis Cluster RateLimiting Service

* [Service Overview](https://dashboards.gitlab.net/d/redis-cluster-ratelimiting-main/redis-cluster-ratelimiting-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22redis-cluster-ratelimiting%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RedisClusterRateLimiting"


<!-- END_MARKER -->

## Summary

The Ratelimiting Redis Cluster instances is a distinct Redis cluster used by RackAttack and Application Rate Limiting
to store the transient rate-limiting counts (almost exclusively a one minute period).  Data has a very short applicable lifespan;
the relevant period is actually stored as part of the keyname (`epoch_time / period`), and it uses Redis TTLs to
manage the data/expiry (no client activity required; old data just ages out)

It is _not_ a service to rate limit requests to Redis itself.

This Redis instance was split off from `redis-cache` because as found in <https://gitlab.com/gitlab-com/gl-infra/production/-/issues/3034#note_460538394> RackAttack
alone accounted for somewhere in the order of 25% (absolute) CPU usage on the redis-cache instance in Nov 2020, and that will
only have grown with traffic.

As the cache cluster approached 95% saturation it was determined the best short-term approach was to split out the rate-limiting
data storage to its own cluster before we go further with more horizontal scalability.

The `redis-cluster-ratelimiting` instance is the horizontally scalable
counterpart of `redis-ratelimiting` whichs runs in Sentinel mode. More
information on efforts to horizontally scale Redis instances can be found [here](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/823).

## Architecture

Redis is in a 3-node-per-shard (single-primary/two-replica per shard) VM configuration, in
cluster mode. The node count will increase as we scale horizontally.

<!-- ## Performance -->

## Scalability

Single threaded CPU is the normal constraint for Redis, and will in particular be the case here.  It is CPU heavy, and _not_ data
heavy. Analysis suggests data volumes are in the order of MBs, not GBs, and small numbers at that.

Redis Cluster is horizontally scalable as decsribed in the
[specifications](https://redis.io/docs/reference/cluster-spec/).

## Availability

The usual redis availability expectations for our 3-node-per-shard clusters apply (see <https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/redis/redis-survival-guide-for-sres.md#high-availability>)

For Redis instances in cluster mode, each shard is made of 1 master node and at
least 2 replica nodes, similar to a Redis sentinel setup.

The availability would depend on the configuration for the Redis instance:

* `cluster-require-full-coverage`: If this is set to yes, as it is by default,
  the cluster stops accepting writes if some percentage of the key space is not
  covered by any node.
* `cluster-allow-reads-when-down`: If this is set to no, as it is by default,
  a node in a Redis Cluster will stop serving all traffic when the cluster is
  marked as failed, either when a node can't reach a quorum of masters or when
  full coverage is not met.

More information can be found
[here](https://redis.io/docs/management/scaling/).

## Durability

Unimportant; data has a (almost exclusively) 1 minute useful period.  If we lost all data in this cluster, within 1 minute (at most) all effects would be passed, and at worst during that 1 minute some users might be able to access the system at up to double the usual rate-limit (an absolute upper limit, depending on which part of the minute the failure happened and the distribution of their requests during that period).

<!-- ## Security/Compliance -->

## Monitoring/Alerting

Uses the same metrics-catalog definitions as for the other Redis clusters.

<!-- ## Links to further Documentation -->
