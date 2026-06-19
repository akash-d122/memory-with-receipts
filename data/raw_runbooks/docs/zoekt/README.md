<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Exact code search Service

* [Service Overview](https://dashboards.gitlab.net/d/zoekt-main/zoekt3a-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22zoekt%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Zoekt"

## Logging

* [Rails](https://log.gprd.gitlab.net/goto/15b83f5a97e93af2496072d4aa53105f)
* [Sidekiq](https://log.gprd.gitlab.net/goto/d7e4791e63d2a2b192514ac821c9f14f)
* [Zoekt Health Dashboard](https://log.gprd.gitlab.net/app/r/s/rtbpx)

<!-- END_MARKER -->

## Summary

### Quick start

GitLab uses [Zoekt](https://github.com/sourcegraph/zoekt), an open-source search engine specifically designed for precise code search. This integration powers GitLab's "exact code search" feature which offers significant improvements over the Elasticsearch-based search, including exact match and regular expression modes.

Our Zoekt integration is supported by:

1. [`gitlab-zoekt-indexer`](https://gitlab.com/gitlab-org/gitlab-zoekt-indexer) a service (written in Go) which manages the underlying Zoekt indexes and provides gRPC (and legacy HTTP) APIs for integrating with GitLab
2. [`gitlab-zoekt` helm chart](https://gitlab.com/gitlab-org/cloud-native/charts/gitlab-zoekt) to deploy the above Go service

Unlike Elasticsearch, which was not ideally suited for code search, Zoekt provides:

* **Exact match mode**: Returns results that precisely match the search query
* **Regular expression mode**: Supports regex patterns and boolean expressions
* **Multiple line matches**: Shows multiple matching lines from the same file
* **Advanced filters**: Language, file path, symbol, etc.

This feature is part of the [epic](https://gitlab.com/groups/gitlab-org/-/epics/9404) to improve code search capabilities in GitLab.

### How-to guides

#### Monitoring Zoekt system state

To get comprehensive information about the current state of the Zoekt system in the production Rails console, use:

```ruby
Search::RakeTask::Zoekt.info(name: "gitlab:zoekt:info", watch_interval: 60)
```

The `watch_interval` parameter refreshes the data every N seconds (in this example, every 60 seconds). If not set, the command will only run once.

This command provides valuable insights into node status, indexing progress, and system health, making it useful for diagnostics and monitoring.

You can also run this command as part of the rake task: `rake "gitlab:zoekt:info[60]"` or `rake gitlab:zoekt:info` (to run it once).

#### Enabling/Disabling Zoekt search

You can prevent GitLab from using Zoekt integration for searching by unchecking the checkbox `Enable searching` under the section `Exact code search` found in the admin [settings](https://gitlab.com/admin/application_settings/search)(accessed by admins only) `Settings->Search`, but leave the indexing integration itself enabled.
An example of when this is useful is during an incident where users are experiencing slow searches or Zoekt is unresponsive.

#### Enabling/Disabling Zoekt search for specific namespaces

When we rollout Zoekt search for SaaS customers, it is enabled by default. But if a customer wish to get it disabled we can run the following chatops command to disable the Zoekt search specifically for a namespace.

```
  /chatops gitlab run feature set --group=root-group-path disable_zoekt_search_for_saas true --production
```

To re-enable it again we can run the following chatops command

```
  /chatops gitlab run feature set --group=root-group-path disable_zoekt_search_for_saas false --production
```

#### Evicting namespaces from a Zoekt node

In order to evict a namespace manually, you can manually delete the `Search::Zoekt::Replica` record associated with the namespace:

```ruby
namespace = Namespace.find_by_full_path('gitlab-org')
enabled_namespace = Search::Zoekt::EnabledNamespace.where(root_namespace_id: namespace.id).first
enabled_namespace.replicas.delete_all
```

#### Marking a zoekt node as lost

When a Zoekt node PVC is over 80% of usage and evicting or removing namespaces doesn't reduce the usage, you can quickly remove all namespaces from a Zoekt node by manually mark the node as lost. This is a safe operation because the lost node will reregister itself as a new node and the [Zoekt Architecture](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/code_search_with_zoekt/) will handle allocating all namespaces and projects.

Warning: The new UUID must not exist in the table.

```ruby
node_name = 'gitlab-gitlab-zoekt-29'
uuid = SecureRandom.uuid

Search::Zoekt::Node.by_name(node_name).update_all(uuid: uuid, last_seen_at: 24.hours.ago)
```

#### When to add a Zoekt node

Increase the number of [Zoekt replicas](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/releases/gitlab/values/gprd.yaml.gotmpl#L5) (nodes) by 20% of total capacity if all Zoekt nodes are above 65% of disk utilization. For example, if there are 22 nodes, add 4.4 (4 nodes).

#### Pausing Zoekt indexing

Zoekt indexing can be paused by checking the checkbox `Pause indexing` under the section `Exact code search` found in the admin [settings](https://gitlab.com/admin/application_settings/advanced_search)(accessed by admins only) `Settings->Search`. An example
of when this is useful is during an incident when there are a large number of indexing Sidekiq jobs failing.

#### Disabling Zoekt indexing

Zoekt indexing can be completely disabled by unchecking the checkbox `Enable indexing` under the section `Exact code search` found in the admin [settings](https://gitlab.com/admin/application_settings/search)(accessed by admins only) `Settings->Search`. Pausing indexing is the preferred method to halt Zoekt indexing.

WARNING:
Indexed data will be stale after indexing is re-enabled. Reindexing from scratch may be necessary to ensure up to date search results.

#### Disabling Zoekt rollout

If there is a bug in rollout logic then zoekt rollout can be stopped by running this chatops command.

```
/chatops gitlab run feature set drop_sidekiq_jobs_Search::Zoekt::RolloutWorker true --production
```

To re-enable it again we can run the following chatops command

```
/chatops gitlab run feature set drop_sidekiq_jobs_Search::Zoekt::RolloutWorker false --production
```

#### Limitations

1. Multiple shards and replication are not supported yet. You can follow the progress in <https://gitlab.com/groups/gitlab-org/-/epics/11382>.

## Architecture

* Design document: <https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/code_search_with_zoekt/>

### Key Components

#### Unified Binary: `gitlab-zoekt`

A significant improvement in the implementation is the introduction of a unified binary called `gitlab-zoekt`, which replaces the previously separate binaries (`gitlab-zoekt-indexer` and `gitlab-zoekt-webserver`). This unified binary can operate in two distinct modes:

* **Indexer mode**: Responsible for indexing repositories
* **Webserver mode**: Responsible for serving search requests

Having a unified binary simplifies deployment, operation, and maintenance of the Zoekt infrastructure. The key advantages of this approach include:

1. **Simplified deployment**: Only one binary needs to be built, deployed, and maintained
2. **Consistent codebase**: Shared code between indexer and webserver is maintained in one place
3. **Operational flexibility**: The same binary can run in different modes based on configuration
4. **Testing mode**: The unified binary can run both services simultaneously for testing purposes

#### Database Models

GitLab uses several database models to manage Zoekt:

* **`Search::Zoekt::EnabledNamespace`**: Tracks which namespaces have Zoekt enabled
* **`Search::Zoekt::Node`**: Represents a Zoekt server node with information about its capacity, address, and online status
* **`Search::Zoekt::Replica`**: Manages replica relationships for high availability
* **`Search::Zoekt::Index`**: Manages the index state for a namespace, including storage allocation and watermark levels
* **`Search::Zoekt::Repository`**: Represents a project repository in Zoekt with indexing state
* **`Search::Zoekt::Task`**: Tracks indexing tasks (index, force_index, delete) that need to be processed by Zoekt nodes

### Communication Flow

#### Indexing Flow

1. GitLab detects repository changes and creates `zoekt_tasks`
2. Zoekt nodes periodically pull tasks via HTTP requests to GitLab's Internal API
3. Zoekt nodes process the tasks (indexing repositories)
4. Zoekt nodes send callbacks to GitLab to update task status
5. Appropriate database records are updated (`zoekt_task`, `zoekt_repository`, `zoekt_index`)

#### Search Flow

1. User performs a search in GitLab UI
2. GitLab determines if the search should use Zoekt
3. If Zoekt is appropriate, GitLab forwards the search to a Zoekt node
4. Zoekt processes the search and returns results
5. GitLab formats and presents the results to the user

### Scaling and High Availability

#### Self-Registering Node Architecture

* Nodes register themselves with GitLab through the task retrieval API
* Each node provides information about its address, name, disk usage, etc.
* GitLab maintains a registry of nodes with their status and capacity
* Nodes that don't check in for a period can be automatically removed

This architecture makes the system self-configuring and facilitates easy scaling.

#### Sharding Strategy

* Groups/namespaces are assigned to specific Zoekt nodes for indexing and searching
* GitLab manages the shard assignments internally based on node capacity and load
* When new nodes are added, they can automatically take on new workloads
* If nodes go offline, their work can be reassigned to other nodes

#### Replication Strategy

* A primary-replica model is used for high availability
* Primary nodes handle both indexing and search
* Replica nodes are used for search only
* Each replica has its own independent index (no complex index file synchronization)
* If a primary goes down, a replica can be promoted to primary

### Zoekt API

#### Task Retrieval API

Zoekt nodes call this endpoint to send heartbeat and get tasks to process:

```
POST /internal/search/zoekt/:uuid/heartbeat
```

This provides node information (UUID, URL, disk space, etc.) and returns tasks that need to be processed.

#### Callback API

Zoekt nodes send callbacks to this endpoint after processing tasks:

```
POST /internal/search/zoekt/:uuid/callback
```

This updates task status (success/failure) and can include additional information like repository size.

#### Search API

GitLab calls this endpoint on Zoekt to execute searches:

```
GET /api/search
```

This includes query parameters and filters and returns search results to be displayed to the user.

### Deployment

#### Kubernetes/Helm

* GitLab provides a Helm chart (`gitlab-zoekt`) for Kubernetes deployments
* The chart deploys Zoekt in a StatefulSet with a persistent volume for index storage
* The chart includes configurations for resource allocation, scaling, and networking
* A gateway component (NGINX) is deployed for load balancing

#### Docker/Container

* Containers are built from the CNG repository
* The Dockerfile builds on top of gitlab-base and includes:
  * The `gitlab-zoekt` unified binary
  * Universal ctags for symbol extraction
  * Scripts for process management and healthchecks
* The container can be configured via environment variables to run in either indexer or webserver mode

## Scalability

### How much Zoekt storage do we need

Worst-case scenario, Zoekt index takes about 2.8 times of the source code in the indexed branch (excluding binary files). We don't observe that in reality. It's usually about 0.4.

### Watermark Management

The Zoekt integration includes a sophisticated watermark management system to ensure efficient use of storage:

1. **Low Watermark (60-70%)**: Triggers rebalancing to avoid reaching higher levels
2. **High Watermark (70-75%)**: Signals potential storage pressure and prioritizes rebalancing
3. **Critical Watermark (85%+)**: May pause indexing to prevent node overload while performing evictions

This system ensures that storage is used efficiently while preventing nodes from running out of space.

## Node Offline and Lost Detection

### Overview

Zoekt implements a two-tier system for handling unavailable nodes:

1. **Offline detection**: Quick detection of unresponsive nodes
2. **Lost node marking**: Automatic data reallocation after extended downtime

This mechanism ensures traffic continuity by reallocating data from lost nodes to healthy nodes while providing safeguards against full cluster outages.

### Offline vs Lost Nodes

#### Offline Nodes

* **Detection threshold**: 30 seconds without heartbeat (hardcoded in [node.rb](https://gitlab.com/gitlab-org/gitlab/-/blob/ae589c78136130900ea1887d4322ce2ed440bb5a/ee/app/models/search/zoekt/node.rb#L12))
* **Heartbeat mechanism**: Nodes check in via the `/internal/search/zoekt/:uuid/heartbeat` API
* **Behavior**: Offline nodes no longer serve search traffic but retain their data
* **Recovery**: Offline nodes can rejoin the cluster with their data intact
* **User experience**:
  * During the first 30 seconds of a node outage, searches against that node may fail or timeout as GitLab attempts to reach the unresponsive node
  * After 30 seconds, the node is marked offline and GitLab will not route search traffic to it
  * Searches automatically fall back to Advanced Search (if available) or Basic Search, ensuring users can still search code while the node is offline or being reallocated

#### Lost Nodes

* **Detection threshold**: Configurable via [admin settings](https://docs.gitlab.com/integration/zoekt/#define-when-offline-nodes-are-automatically-deleted)
  * **Default**: 12 hours
  * **Production setting**: 10 minutes (as of latest configuration)
* **Behavior**: Lost nodes trigger data reallocation to healthy nodes
* **Recovery**: If a node is already marked as lost, it will be wiped when it rejoins the cluster
* **Safeguard**: Nodes will not be marked as lost if all nodes in the cluster are offline (prevents data loss during cluster-wide incidents)

### Data Recovery Process

When nodes are marked as lost:

1. **Data reallocation**: Zoekt indices are reassigned to healthy online nodes
2. **Reindexing**: Affected namespaces are reindexed on the new nodes
3. **Source of truth**: Gitaly serves as the SSOT for all data
4. **Performance**: Reindexing is fast and efficient for small numbers of nodes. The number of concurrent indexing tasks per node is determined by `GOMAXPROCS` (based on available CPUs) multiplied by the indexing CPU to tasks multiplier ([configurable](https://docs.gitlab.com/integration/zoekt/#set-concurrent-indexing-tasks), default 1.0). For reference, indexing a large repository like `gitlab-org/gitlab` from scratch takes approximately 10-20 seconds.

#### Impact on Gitaly

* **Normal operation**: Even full .com reindexing (48TiB+) does not overload Gitaly
* **Risk scenario**: Large portions of the fleet going offline simultaneously could create higher Gitaly load
* **Mitigation**: The safeguard preventing loss marking when all nodes are offline helps prevent this scenario

### When to Adjust Settings

Consider increasing the lost node detection threshold (currently 10 minutes) if:

* Frequent node restarts are expected (e.g., during deployments or maintenance)
* You need more time to investigate node issues before data reallocation
* Network instability causes temporary connectivity issues

The setting can be adjusted in the admin panel under `Settings->Search->Exact code search`.

## Reindexing from Scratch

### Expected Timeline

When performing a full reindex of GitLab.com from scratch, expect the following timeline:

* **~48 hours**: The majority of repositories will be reindexed
* **Several days**: Long tail of larger repositories may take additional time

These estimates are based on historical reindexing operations and may vary depending on:

* Number of Zoekt nodes available
* Size and number of repositories being indexed
* Current system load

### Monitoring Reindexing Progress

During a reindexing operation, use these tools to monitor progress:

1. **Rake task**: Run the monitoring command to get real-time status:

   ```shell
   # Run once
   rake gitlab:zoekt:info

   # Or with auto-refresh every 60 seconds
   rake "gitlab:zoekt:info[60]"
   ```

   Alternatively, in a Rails console:

   ```ruby
   Search::RakeTask::Zoekt.info(name: "gitlab:zoekt:info", watch_interval: 60)
   ```

2. **Dashboards**:
   * [Zoekt Overview Dashboard](https://dashboards.gitlab.net/d/zoekt-main/zoekt3a-overview) (Grafana): Monitor overall indexing progress and system health
   * [Zoekt Health Dashboard](https://log.gprd.gitlab.net/app/r/s/biFwz) (Kibana): Monitor search and indexing operations

### What to Expect During Reindexing

* **Search availability**: Search results will be incomplete until reindexing completes. Users may not find results for repositories that haven't been reindexed yet.
* **Increased resource usage**: Expect higher CPU, memory, and disk I/O on Zoekt nodes during reindexing.
* **Gradual progress**: Indexing progress is not linear. Smaller repositories index quickly, while larger repositories take longer.

## Monitoring

### Dashboards

There are a few dashboards to monitor Zoekt health:

* [Zoekt Health Dashboard](https://log.gprd.gitlab.net/app/r/s/jR5H5): Monitor search and indexing operations
* [Zoekt memory usage](https://thanos-query.ops.gitlab.net/graph?g0.expr=sum(process_resident_memory_bytes%7Benv%3D%22gprd%22,%20container%3D~%22zoekt.*%22%7D)%20by%20(container,%20pod)&g0.tab=0&g0.stacked=0&g0.range_input=2h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D&g0.step_input=60) : View memory utilization for Zoekt containers
* [Zoekt OOM errors](https://thanos.gitlab.net/graph?g0.expr=(sum%20by%20(container%2C%20pod%2C%20environment)%20(kube_pod_container_status_last_terminated_reason%7Benv%3D%22gprd%22%2C%20cluster%3D%22gprd-gitlab-gke%22%2C%20pod%3D~%22gitlab-gitlab-zoekt-%5B0-9%5D%2B%22%2C%20reason%3D%22OOMKilled%22%7D)%0A%20%20%20%20%20%20*%20on%20(container%2C%20pod%2C%20environment)%20group_left%0A%20%20%20%20%20%20sum%20by%20(container%2C%20pod%2C%20environment)%20(changes(kube_pod_container_status_restarts_total%7Benv%3D%22gprd%22%2C%20cluster%3D%22gprd-gitlab-gke%22%2C%20pod%3D~%22gitlab-gitlab-zoekt-%5B0-9%5D%2B%22%7D%5B1m%5D)%20%3E%200))%0A&g0.tab=0&g0.stacked=0&g0.range_input=12h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D): View any Out Of Memory exceptions for Zoekt containrs
* [Zoekt pvc usage](https://dashboards.gitlab.net/goto/tnRv54jSR?orgId=1): View PVC volume capacity for Zoekt nodes
* [Zoekt indexing locks in progress](https://dashboards.gitlab.net/goto/ugHccVjIR?orgId=1): View number of indexing locks (locks are per project)
* [Zoekt Info Dashboard](https://dashboards.gitlab.net/d/search-zoekt/search3a-zoekt-info)

### Kibana logs

GitLab application has a dedicated `zoekt.log` file for Zoekt-related log entries. This will be handled by the standard logging infrastructure. You may also find indexing related errors in `sidekiq.log` and search related errors in `production_json.log`.

The `gitlab-zoekt` binary (in both indexer and webserver modes) writes logs to stdout.

## Alerts

### `kube_persistent_volume_claim_disk_space`

[Zoekt architecture](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/code_search_with_zoekt/) has logic which detects when nodes disk usage is over the limit. Projects will be removed from each node until it the node disk usage under the limit. If the disk space is not coming down quick enough, follow these steps in order:

1. [remove namespaces manually](#evicting-namespaces-from-a-zoekt-node)
1. As a last resort, [mark the node as lost](#marking-a-zoekt-node-as-lost)

WARNING: The PVC disk size must not be increased manually. Zoekt nodes are sized with a specific PVC size and it must remain consistant across all nodes.
