<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Redis TraceChunks Service

* [Service Overview](https://dashboards.gitlab.net/d/redis-tracechunks-main/redis-tracechunks-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22redis-tracechunks%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RedisTraceChunks"

## Logging

* [system](https://log.gprd.gitlab.net/goto/a10c2cd2b710f9eb65b13b9a2a328d51)

<!-- END_MARKER -->

<!-- ## Summary -->

The TraceChunks redis instances is a distinct redis cluster for storing CI build trace chunks immediately when received by the API from runners, before they are asynchronously (Ci::BuildTraceChunkFlushWorker) moved from there to ObjectStorage (as configured in .com; the database is another target option, but we don't do that anymore).  The data is important and persistent but transient (seconds to 10s of seconds normally, probably not minutes, definitely not hours, unless something has gone horribly wrong).

This was split because as found in <https://gitlab.com/gitlab-org/gitlab/-/issues/327469#note_556531587> these trace chunks were (at the time) responsible for about 60% of the network throughput by bytes on the persistent redis, and 16% of the Redis calls, and it is a distinctive enough workload/usage pattern that splitting it out was deemed a good thing.

<!-- ## Architecture -->

Redis is in the usual 3-node single-primary/two-replica VM configuration, with sentinels on the same VMs as Redis (as for persistent and sidekiq clusters)

<!-- ## Performance -->

<!-- ## Scalability -->

Single threaded CPU is the normal constraint for Redis but due to the large data transfers networking _may_ become a constraint before CPU does on this cluster, although there is a _lot_ of headroom (2 orders of magnitude)  at this writing (2021) and scaling up the instances is possible to obtain more (or maybe the limits will be higher by then)

<!-- ## Availability -->

The usual persistent redis availability expectations for our 3-node clusters apply (see <https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/redis/redis-survival-guide-for-sres.md#high-availability> )

<!-- ## Durability -->

Data is expected to be largely persistent; some data loss may occur during an unplanned failover event, but in all normal operations all data in this instance is expected to be fully durable.

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

Uses mostly the same metrics-catalog definitions as for the other Redis clusters, except for memory saturation which is deliberately set very low; the transient nature of the data here means any build up is abnormal and should be investigated early while it is easier to recover from.

<!-- ## Links to further Documentation -->

* Implementation/migration epic: <https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/462>
