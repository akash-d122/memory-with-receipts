<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Redis Cluster Sessions Service

* [Service Overview](https://dashboards.gitlab.net/d/redis-cluster-sessions-main/redis-cluster-sessions-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22redis-cluster-sessions%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RedisClusterSessions"


<!-- END_MARKER -->

## Summary

The Sessions Redis instances are a distinct Redis used by Rails for web session storage/handling.  Per-session storage is typically fairly small (hundreds of bytes), but there are a lot of them, they are touched a lot by active users, and some can be big either naturally or unexpectedly.

## Durability

Session data is an interesting hybrid; we do _generally_ want durability/persistence, but can tolerate some loss of data (generally a log-out for affected users).  As such while we persist to disk with RDB, we also have maxmemory and an eviction policy (volatile-ttl) that will, if necessary, evict data with the shortest TTL remaining (sessions that were close to expiry anyway).  Alerting is set to tell us if we are approaching that state of affairs, but that policy gives us space to mitigate/manage the situation without disaster.

## Monitoring/Alerting

Generally the same as other Redis clusters, but with special handling for monitoring maximum memory (as a proportion of the configured limit, not the system limit), and alerting if redis_evicted_keys_total raises above zero (meaning we missed memory saturation)

<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

<!-- ## Links to further Documentation -->
