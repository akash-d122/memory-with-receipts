<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Redis Cluster Chat Cache Service

* [Service Overview](https://dashboards.gitlab.net/d/redis-cluster-chat-cache-main/redis-cluster-chat-cache-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22redis-cluster-chat-cache%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RedisClusterChatCache"


<!-- END_MARKER -->

<!-- ## Summary -->

The Chat Cache Redis Cluster instances is a distinct Redis Cluster used by the GitLab Rails [chat features](https://gitlab.com/gitlab-org/gitlab/-/issues/410521).

<!-- ## Architecture -->

Redis is in a 3-node-per-shard (single-primary/two-replica per shard) VM configuration, in cluster mode. The node count will start off at 3 but will increase as we scale horizontally.

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

Uses the same metrics-catalog definitions as for the other Redis clusters.

<!-- ## Links to further Documentation -->
