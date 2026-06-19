# ActiveContext

## Purpose

ActiveContext enables AI-powered features that understand your codebase by indexing code files into searchable embeddings. The system chunks code files into logical segments, generates vector embeddings for each chunk, and stores them in a vector database (Elasticsearch, OpenSearch, PostgreSQL with pgvector). This enables Retrieval Augmented Generation (RAG) features like [Codebase as Chat Context](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/codebase_as_chat_context/) in GitLab Duo, where the AI can semantically search your code to provide contextually relevant responses to your questions.

## Quick start

### Concepts

#### ActiveContext Abstraction Layer

The ActiveContext is an abstraction layer over different vector stores used for embeddings indexing, search, and other operations.
See the [Design Document](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/ai_context_abstraction_layer/)
and [How It Works](https://gitlab.com/gitlab-org/gitlab/-/blob/master/gems/gitlab-active-context/doc/how_it_works.md) for an overview.

There are 2 ActiveContext workers:

- [`Ai::ActiveContext::MigrationWorker`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/workers/ai/active_context/migration_worker.rb):
runs every 5 minutes and picks up [new migrations](https://gitlab.com/gitlab-org/gitlab/-/blob/master/gems/gitlab-active-context/doc/migrations.md)
- [`Ai::ActiveContext::BulkProcessWorker`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/workers/ai/active_context/bulk_process_worker.rb):
runs every minute and processes documents queued for embeddings generation

#### Code Embeddings Pipeline

The Code Embeddings Pipeline is an embeddings indexing pipeline for project code files that makes use of the ActiveContext abstraction layer.
See the [Design Document](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/codebase_as_chat_context/code_embeddings/) for an architecture overview.

The workers in the Code Embeddings Pipeline are scheduled through the [`Ai::ActiveContext::Code::SchedulingWorker`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/workers/ai/active_context/code/scheduling_worker.rb). The `SchedulingWorker` runs every minute and checks which workers defined in the [`Ai::ActiveContext::Code::SchedulingService`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/services/ai/active_context/code/scheduling_service.rb) are due to run. For further details, please refer to the [Index State Management section in the Design Document](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/codebase_as_chat_context/code_embeddings/#index-state-management).

#### AI Gateway Embeddings Generation Requests

ActiveContext pipelines send embeddings generation requests to the AI Gateway.

The Code Embeddings Pipeline uses Vertex AI's `text-embedding-005` model and sends embeddings generation requests through the AI Gateway Vertex AI proxy endpoint: `/v1/proxy/vertex-ai/`.

### Related resources

- [Advanced Search runbook](../elastic/advanced-search-in-gitlab.md)

## How-to guides

### Start ActiveContext indexing

To start running the ActiveContext indexing pipelines, you need to [create an `Ai::ActiveContext::Connection` record](https://gitlab.com/gitlab-org/gitlab/-/blob/master/gems/gitlab-active-context/doc/getting_started.md#create-a-connection) then [activate it](https://gitlab.com/gitlab-org/gitlab/-/blob/master/gems/gitlab-active-context/doc/getting_started.md#activate-a-connection). This ensures that the pipeline workers (for example, the ones defined in [`Ai::ActiveContext::Code::SchedulingService`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/services/ai/active_context/code/scheduling_service.rb#L6)) will proceed to run.

### Check indexing status

Use the `gitlab:semantic_search:code:info` rake task to display the current status of Semantic Code Search, including indexing status, vector store connection details, repository statistics, and embedding queue sizes.

```shell
sudo gitlab-rake gitlab:semantic_search:code:info
```

To monitor status continuously, provide a watch interval in seconds:

```shell
sudo gitlab-rake "gitlab:semantic_search:code:info[5]"
```

Press `Ctrl+C` to stop.

Example output:

```
Semantic Code Search
Indexing enabled:               yes
Indexing active:                yes

Connection:
  Name:                         elasticsearch
  Adapter:                      ActiveContext::Databases::Elasticsearch::Adapter
  Active:                       yes

Repositories
Total:                          42
Ready:                          40 (95%)
Pending:                        1 (2%)
Code indexing in progress:      1 (2%)
Embedding indexing in progress: 0 (0%)
Failed:                         0 (0%)

Embedding Queues
Code queue:                     5
  Shard count:                  1
  Shard limit:                  1000
Backfill queue:                 0
  Shard count:                  1
  Shard limit:                  1000
Retry queue:                    0
Dead queue:                     0
```

See also: [Semantic code search documentation](https://docs.gitlab.com/user/gitlab_duo/semantic_code_search/#check-indexing-status)

### Pause the `Ai::ActiveContext::MigrationWorker`

To pause the `MigrationWorker`, you can use [Sidekiq Chatops command to drop jobs]:

```
/chatops gitlab run feature set drop_sidekiq_jobs_Ai::ActiveContext::MigrationWorker true --ignore-feature-flag-consistency-check
```

To un-pause/restart, simply delete the drop-job Feature Flag:

```
/chatops gitlab run feature delete drop_sidekiq_jobs_Ai::ActiveContext::MigrationWorker --ignore-feature-flag-consistency-check
```

### Pause Indexing

This pauses workers that have operations that access the vector store, ensuring that we avoid data loss during maintenance tasks in the vector store (like upgrades).

ActiveContext indexing is paused when either of the following settings is `true`:

- `active_context_pause_indexing` — dedicated ActiveContext pause setting (added in [gitlab-org/gitlab!229832](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/229832))
- `elasticsearch_pause_indexing` — global legacy setting (also pauses Advanced Search)

To pause only ActiveContext indexing without affecting Advanced Search, use the Admin API:

```shell
curl --request PUT \
  --header "PRIVATE-TOKEN: <your_token>" \
  --data "active_context_pause_indexing=true" \
  "https://gitlab.com/api/v4/application/settings"
```

Or via Rails console:

```ruby
ApplicationSetting.current.update!(active_context_pause_indexing: true)
```

To resume:

```ruby
ApplicationSetting.current.update!(active_context_pause_indexing: false)
```

You can verify the current state with:

```ruby
Gitlab::CurrentSettings.active_context_indexing_paused?
```

Note: if `elasticsearch_pause_indexing` is also `true`, ActiveContext indexing will remain paused even if `active_context_pause_indexing` is `false`. To pause both ActiveContext and Advanced Search indexing at once, see the [Advanced Search runbook](../elastic/README.md#upgrade-checklist).

### Clear the dead queue

The dead queue holds items that have failed processing twice (code queue → retry queue → dead queue)
and are never automatically reprocessed. If the dead queue size is non-zero (visible in the
`gitlab:semantic_search:code:info` output under `Embedding Queues`), you can discard all stranded items:

```
/chatops run active_context dead_queue clear
```

Expected output:

```
Cleared 42 items from the ActiveContext dead queue.
```

To replay the items into a processing queue instead of discarding them, see
[Replay the dead queue](#replay-the-dead-queue).

### Replay the dead queue

Instead of discarding dead queue items, you can replay them back into a processing queue. The `--queue`
argument is required and must be one of the registered queue names (`retry_queue`, `code`,
`code_backfill`).

The recommended target is `retry_queue`, which attempts processing once more before potentially
failing back to the dead queue:

```
/chatops run active_context dead_queue replay --queue=retry_queue
```

To replay directly into the main code queue (re-runs the full embedding pipeline):

```
/chatops run active_context dead_queue replay --queue=code
```

Expected output:

```
Replayed 38 items from the dead queue into 'retry_queue'.
```

If an invalid queue name is provided, the command returns the list of valid queue names.

To discard items instead of replaying them, see [Clear the dead queue](#clear-the-dead-queue).

### Toggle ActiveContext indexing

You can toggle ActiveContext indexing by deactivating or activating the relevant `Ai::ActiveContext::Connection`.

**To deactivate the active connection**

This stops all ActiveContext-related workers.

⚠️ _WARNING: This is a destructive action that will require a full reindex and should be used as a last resort. [Pause indexing](#pause-indexing) is the preferred method to use during incidents or maintenance._

```ruby
Ai::ActiveContext::Connection.active.deactivate!
```

**To reactivate a connection**

⚠️ _WARNING: if there is already an existing active connection, this will deactivate that other connection._

```ruby
conn = Ai::ActiveContext::Connection.find_by(name: 'elastic')
conn.activate!
```

## Monitoring

### ActiveContext pipelines

#### Dashboard

- [Code Indexing and Embeddings pipeline](https://log.gprd.gitlab.net/app/r/s/gUAYt)

#### Logs

_These are the same logs from the dashboard visualizations._

**Code: Index State Management**

- [SaasInitialIndexingEventWorker](https://log.gprd.gitlab.net/app/r/s/6acBD) - This worker marks namespaces as `ready` for ad-hoc indexing.
- [ProcessPendingEnabledNamespaceEventWorker](https://log.gprd.gitlab.net/app/r/s/gvIqd) - This worker is not run in the regular pipeline with ad-hoc indexing. It processes `pending` namespaces, preparing the projects in the namespace for initial indexing.
- [AdHocIndexingWorker](https://log.gprd.gitlab.net/app/r/s/EUbmk) - This worker kicks off initial indexing for a project ad-hoc. It is triggered on the first time a semantic search is performed on a project.
- [MarkRepositoryAsReadyEventWorker](https://log.gprd.gitlab.net/app/r/s/Iv77N) - Once Initial Indexing is completed, this worker marks a project as `ready`. This means that the project is ready for subsequent Incremental Indexing after pushes or merges to the default branch.
- [RepositoryIndexWorker](https://log.gprd.gitlab.net/app/r/s/DTBYk) - This worker executes indexing per repository. This includes both INITIAL and INCREMENTAL indexing.
  - [Initial Indexing Service](https://log.gprd.gitlab.net/app/r/s/Zoy3d) - triggered by the `ProcessPendingEnabledNamespaceEventWorker` for eligible projects
  - [Incremental Indexing Service](https://log.gprd.gitlab.net/app/r/s/Zs176) - after a project has been initially indexed and marked as `ready`, triggered after commits are pushed or merged to the default branch
  - [Code Indexer](https://log.gprd.gitlab.net/app/r/s/zs4bt) - this is the actual class that calls the `gitlab-elasticsearch-indexer`

**Code: Embeddings Generation**

- [BulkProcessWorker](https://log.gprd.gitlab.net/app/r/s/sSDKo) - This will allow you to trace the embeddings generation process.
  - [Jobs](https://log.gprd.gitlab.net/app/r/s/0mzZn) - Tracks the start and finish of the bulk processing jobs
  - [Embeddings Generation requests](https://log.gprd.gitlab.net/app/r/s/fmAZB) - Tracks the actual call to the embeddings generation model (`Gitlab::Llm::VertexAi::Client`)
  - [Error log](https://log.gprd.gitlab.net/app/r/s/6A36M) - Errors encountered during the bulk embeddings generation process
    - `ContentNotFoundError` - logged as a warning and the document is skipped
    - Other errors - logged as a warning and the documents are re-queued for processing

### AI Gateway

These are AI Gateway logs and dashboards that are relevant to ActiveContext Code Embeddings pipeline.

- [Log: embeddings generations for Vertex AI `text-embedding-005`](https://log.gprd.gitlab.net/app/r/s/Kthi3)
- [Dashboard: Vertex AI GCP Quota](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway-overview?orgId=1&viewPanel=1515902021)
