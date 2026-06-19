# Redis Cluster

## Core concepts

Redis Cluster is a mode of Redis to enable horizontal scaling. The dataset is divided among multiple nodes, allowing the computational load to be distributed.

How does Redis Cluster differ from non-clustered Sentinel-based Redis instances?

| Property | Sentinel | Cluster |
| --------- | ------ | ------ |
| Dataset | Every node has the entire dataset | Distributed over `n` nodes |
| Computation | Performed by master node | Performed by respective hash slot owner |
| Operations | All standard operations allowed | Cross-slot operations are not permitted |
| Scalability | Only vertical scaling | Increase cluster's shard size |
| Failovers | Coordinated by Sentinels | Coordinated by a quorum of master nodes |

References

- [Redis Cluster Specifications](https://redis.io/docs/reference/cluster-spec/)
- [Redis Cluster Scaling](https://redis.io/docs/management/scaling/)

## Glossary

**cluster**: A set of Redis nodes running in cluster-enabled mode.  In cluster mode, there are no Sentinel sidecar processes to perform monitoring, routing, and failover.  Instead, each Redis node communicates with all of its peers in a mesh, and clients are cluster-aware, connecting directly to these nodes.  In addition to the standard port that clients use, Redis nodes also use a "cluster bus" gossip protocol (on standard port + 10000) to exchange messages about cluster config updates, failure detection, failover authorization, etc. (see all gossip message types).

**shard**:In Redis Cluster, a shard is a discrete set of hash slots (defined below), owned by a group of Redis nodes (a master node and its replicas).  In some discussions we have alternately called this a "replica set", to distinguish it from our historical use of the term "shard" to represent client-managed "functional partitions" (where clients send certain keys to purpose-specific Redis targets such as `redis-sidekiq`, `redis-tracechunks`, etc.).

**node**: A single redis-server process, acting in either a master or replica role.  A Redis Cluster consists of a set of such nodes.  The cluster aims to have every hash slot owned by exactly 1 master (many-to-one), and each replica replicates the entirety of a single master (using the same async replication mechanism as with our current Sentinel-managed Redis nodes).  The cluster can dynamically reassign a node's role to compensate for node or connectivity failures, with the goal of ensuring that all hash slots are assigned to a healthy master node and all master nodes have a target number of replicas.

**hash slot**: The smallest unit of sharding. Every Redis Cluster has exactly 16384 hash slots.  Groups of hash slots are assigned as non-overlapping ranges to Redis master nodes (and their replicas).  Example:

```
Master[0] -> Slots 0 - 5460
Master[1] -> Slots 5461 - 10922
Master[2] -> Slots 10923 - 16383
```

Redis determines which shard stores a key by mapping that key to a hash slot using the [crc16 hash of the key or its hash](https://github.com/redis/redis/blob/7.0.7/src/cluster.c#L927-L952) tag and then checking which master node owns that hash slot.  The dictionary mapping hash slots to master nodes is locally cached by clients, and if a client's cached dictionary becomes out of date, Redis will redirect the client to the appropriate node, allowing the client to update its dictionary for future operations.

**cross-slot operations**: Multi-key commands containing keys which map to different hash slots. Any operations involving keys of different hash slot are deemed unsafe by Redis Cluster and rejected. For example, an `MGET` for keys of different hash slot is not possible to be served by a single master node since it may not own all the required hash slots.

**resharding**:  Migrating ownership of some hash slots from one shard to another.  This is a dynamic online operation, where Redis keys are migrated between nodes.  During a resharding operation, reads and writes to the keys being migrated are semantically safe but incur some extra overhead.  Also, multi-key requests may temporarily fail during the transitional state.  There are some documented corner cases where a failed resharding attempt must be manually completed.  In our environments, because we do not intend to dynamically add/remove nodes, resharding will be a rare and planned event (e.g. when adding new nodes to the cluster for additional capacity), not a frequent automated background activity.

replica migration - an optional feature that allows the cluster to dynamically reassign a replica from one master to another, to ensure all masters have at least N replicas.  This feature aims to improve availability.  However, it can counter-intuitively harm availability in either of 2 ways: it can lead to a master and its replicas being in the same availability zone ([details](https://gitlab.com/gitlab-com/gl-infra/scalability/-/issues/1962#note_1140700451)), or it can lead to accumulating a majority of masters in the same availability zone ([details](https://gitlab.com/gitlab-com/gl-infra/scalability/-/issues/1962#note_1140436657)).  This feature can be disabled ([cluster-allow-replica-migration](https://github.com/redis/redis/blob/7.0.7/redis.conf#L1662-L1668)) or tuned ([cluster-migration-barrier](https://github.com/redis/redis/blob/7.0.7/redis.conf#L1642-L1660)).  This is one of the topics to be addressed by scalability#2071.

## Observability

For most parts, the Grafana dashboard is the same as a Sentinel-based Redis dashboard. The difference lies in:

1. Cluster-specific panel: This panel tracks the slot coverage and state of nodes in the cluster. The components are defined in [`libsonnet/gitlab-dashboards/redis_common_graphs.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/ff4ff9dd29ee417a4a7d1940178c3085cc25730f/libsonnet/gitlab-dashboards/redis_common_graphs.libsonnet#L449).
2. `cluster_redirection` error SLI - tracks the rate of MOVED and ASK redirections. Redirections should only happen on (1) failover (requests are redirected to the new master), (2) resharding (requests are redirected to the new slot owner).

Cross-slot errors are prevented on the application side and should not reach the servers except for pipelined operations during resharding. The volume can be tracked on logs under 2 groups of fields:

1. `json.redis_<functional shard>_allowed_cross_slot_calls` shows the volume of [allowed](https://gitlab.com/gitlab-org/gitlab/-/blob/92312944bb8a827b5d00509a5d07d0fe8ee4955d/lib/gitlab/instrumentation/redis_cluster_validator.rb#L205) cross-slot calls (i.e. commands are accounted for and are running on non-cluster-based Redis)
2. `json.redis_<functional_shard>_cross_slot_calls` shows the volume of cross-slot commands (not accounted for or running on Redis Cluster)

## Troubleshooting

### What is the state of the cluster?

Some commands to understand the overall state:

- `CLUSTER NODES`
- `CLUSTER INFO`
- `CLUSTER SLAVES`

`CLUSTER NODES` provides a quick summary of node information. Look out for the connection state of each node (look out for the `connected` keyword) and the number of masters.

```
07c37dfeb235213a872192d90877d0cd55635b91 127.0.0.1:30004@31004,,shard-id=69bc080733d1355567173199cff4a6a039a2f024 slave e7d1eecce10fd6bb5eb35b9f99a514335d9ba9ca 0 1426238317239 4 connected
67ed2db8d677e59ec4a4cefb06858cf2a1a89fa1 127.0.0.1:30002@31002,,shard-id=114f6674a35b84949fe567f5dfd41415ee776261 master - 0 1426238316232 2 connected 5461-10922
292f8b365bb7edb5e285caf0b7e6ddc7265d2f4f 127.0.0.1:30003@31003,,shard-id=fdb36c73e72dd027bc19811b7c219ef6e55c550e master - 0 1426238318243 3 connected 10923-16383
6ec23923021cf3ffec47632106199cb7f496ce01 127.0.0.1:30005@31005,,shard-id=114f6674a35b84949fe567f5dfd41415ee776261 slave 67ed2db8d677e59ec4a4cefb06858cf2a1a89fa1 0 1426238316232 5 connected
824fe116063bc5fcf9f4ffd895bc17aee7731ac3 127.0.0.1:30006@31006,,shard-id=fdb36c73e72dd027bc19811b7c219ef6e55c550e slave 292f8b365bb7edb5e285caf0b7e6ddc7265d2f4f 0 1426238317741 6 connected
e7d1eecce10fd6bb5eb35b9f99a514335d9ba9ca 127.0.0.1:30001@31001,,shard-id=69bc080733d1355567173199cff4a6a039a2f024 myself,master - 0 0 1 connected 0-5460
```

`CLUSTER INFO` gives a fast overview of the state. If `cluster_state:ok` and `cluster_slots_ok:16384` are present, the cluster is likely to be fine.

```
➜  ~ redis-cli cluster info
cluster_state:ok
cluster_slots_assigned:16384
cluster_slots_ok:16384
cluster_slots_pfail:0
cluster_slots_fail:0
cluster_known_nodes:9
cluster_size:3
```

`CLUSTER SLAVES <node id>` provides shard-based information when wanting to drill down to a specific master node.

```
➜  ~ redis-cli -p 7001 cluster slaves 97d7d00217fb53b9f4f74763f04be50c536dc470
1) "4ccb0580c355ff37d54665f7f60fe00a5ee9a6c9 127.0.0.1:7202@17202,localhost slave 97d7d00217fb53b9f4f74763f04be50c536dc470 0 1678417677554 8 connected"
2) "03f7a03ea54ad3d0f8e079e1e63422ec0735046f 127.0.0.1:7203@17203,localhost slave 97d7d00217fb53b9f4f74763f04be50c536dc470 0 1678417677000 8 connected"`
```

To avoid an erroneous single-sided view, the command should be performed on at least 1 nodes from each shards.

For slot health, use `CLUSTER SLOTS` or `CLUSTER SHARDS`.

### How to initialize a new cluster

To initialize a cluster, see the [official Redis guide](https://redis.io/docs/management/scaling/#create-a-redis-cluster).

An example of how previous clusters were set up can be found in [here](https://gitlab.com/gitlab-com/gl-infra/scalability/-/issues/2210#note_1287069028).

### How to recover from all nodes going down

As the [gitlab-redis-cluster cookbook](https://gitlab.com/gitlab-cookbooks/gitlab-redis-cluster/-/blob/3dd0f008677d7e85121fe659428adcfc1277e904/attributes/default.rb#L14) defines a `cluster-config-file`, the nodes will attempt to recreate the original cluster topology using previously stored information from the file after a restart.

### How to force promotion of a replica in an emergency where Redis cannot heal itself

There is a sidecar process in each VM which checks the cluster health and forces a failover. See the [originating issue](https://gitlab.com/gitlab-com/gl-infra/scalability/-/issues/2140) for more information.

In the event where the sidecar processes are not working, the SRE/EOC will need to run the [`CLUSTER FAILOVER`](https://redis.io/commands/cluster-failover/) command on the desired slave node to promote that node into a master.

Run the following command on the desired node:

```
sudo gitlab-redis-cli CLUSTER FAILOVER TAKEOVER
```

### How to do online resharding (with warnings)?

See the [official Redis guide](https://redis.io/docs/management/scaling/#reshard-the-cluster).

### How do we rotate passwords in the ACL list?

TODO
