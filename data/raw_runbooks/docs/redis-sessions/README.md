<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Redis Sessions Service

* [Service Overview](https://dashboards.gitlab.net/d/redis-sessions-main/redis-sessions-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22redis-sessions%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RedisSessions"

## Logging

* [system](https://log.gprd.gitlab.net/goto/e9073e6e3b9eb444a47e2a396d711c22)

## Troubleshooting Pointers

* [A survival guide for SREs to working with Redis at GitLab](../redis/redis-survival-guide-for-sres.md)
* [../redis/redis.md](../redis/redis.md)
<!-- END_MARKER -->

## Summary

The Sessions Redis instances are a distinct Redis used by Rails for web session storage/handling.  Per-session storage is typically fairly small (hundreds of bytes), but there are a lot of them, they are touched a lot by active users, and some can be big either naturally or unexpectedly.

## Architecture

Redis is deployed in the usual 3-node single-primary/two-replica VM configuration, with sentinels on the same VMs as Redis.

<!-- ## Performance -->

## Scalability

Single threaded CPU is the normal constraint for Redis, but at initial move we are anticipating something in the order of 20% absolute CPU usage.  Data storage for sessions is in the order of 10GB (at end of 2021).

## Availability

The usual redis availability expectations for our 3-node clusters apply (see <https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/redis/redis-survival-guide-for-sres.md#high-availability> )

## Durability

Session data is an interesting hybrid; we do _generally_ want durability/persistence, but can tolerate some loss of data (generally a log-out for affected users).  As such while we persist to disk with RDB, we also have maxmemory and an eviction policy (volatile-ttl) that will, if necessary, evict data with the shortest TTL remaining (sessions that were close to expiry anyway).  Alerting is set to tell us if we are approaching that state of affairs, but that policy gives us space to mitigate/manage the situation without disaster.

<!-- ## Security/Compliance -->

## Monitoring/Alerting

Generally the same as other Redis clusters, but with special handling for monitoring maximum memory (as a proportion of the configured limit, not the system limit), and alerting if redis_evicted_keys_total raises above zero (meaning we missed memory saturation)

<!-- ## Links to further Documentation -->
