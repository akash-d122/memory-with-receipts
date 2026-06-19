<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Remote Development Workspaces Service

* [Service Overview](https://dashboards.gitlab.net/d/stage-groups-remote_development)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22workspaces%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::workspaces"

## Logging

* [Rails](https://log.gprd.gitlab.net/app/r/s/cfU5g)

<!-- END_MARKER -->
# Workspaces

## About Workspaces

### Contact Information

* **Group**: Create:Remote Development
* **Handbook**: [Remote Development](https://handbook.gitlab.com/handbook/engineering/development/dev/create/remote-development/)
* **Group Slack channel**: [#g_create_remote_development](https://gitlab.enterprise.slack.com/archives/CJS40SLJE)
* **Feature Slack channel**: [#f_workspaces](https://gitlab.enterprise.slack.com/archives/C03KE0L9NC9)

### Architecture Overview

* Workspaces are Kubernetes Pods created in the customer's Kubernetes cluster.
* The Kuberenetes cluster is connected to GitLab by the GitLab Agent for Kubernetes(agentk). GitLab Relay (KAS) proxies this connection.
* The `remote_development` module of GitLab Agent for Kubernetes(agentk) runs a reconciliation loop with GitLab. It sends the information of the actual state of the workspaces in each request. Rails persists this information and responds back with the desired state of workspaces. The agentk acts on the response by applying the Kuberentes manifests received.
* Accessing the workspace is protected by Gitlab Workspaces Proxy installed in the customer's Kubernetes cluster which authenticates and authorizes the request before forwarding it to the workspaces.
* Each worksapce is injected with GitLab VS Code fork for Workspaces which is sideloaded with the GitLab Workflow VS Code extension.
* On workspace creation, the project from which the workspace is created is cloned. If SSHD is present, it will be started.

### Core Functionality

* Isolated sandbox environments running on customer's infrastructure.
* GitLab VS Code fork for Workspaces is accessible over the browser which connects to the VS Code Remote Extension Host running inside the workspace.
* Accessing the servers running inside the workspace through the browser or over SSH.
* AI features like Duo Chat and Code Suggestions powered through the GitLab Workflow VS Code extension.

### Requirements

* Available for Premium or Ultimate subscription
* Available on gitlab.com, dedicated and self-managed instances. For all the offerings, customers are expected to bring their own infrastructure for hosting Workspaces.

### Documentation

* Docs
  * [Workspaces GitLab User Documentation](https://docs.gitlab.com/user/workspace/)
  * [Architecture Design Document](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/workspaces/)
  * [Workspaces category developer documentation repo](https://gitlab.com/gitlab-org/workspaces/gitlab-workspaces-docs)
  * [Developer Guidelines](https://docs.gitlab.com/development/remote_development/) (work in progress, needs to be migrated from [Workspaces category developer documentation repo](https://gitlab.com/gitlab-org/workspaces/gitlab-workspaces-docs))
  * [Workspaces Domain Developer README doc](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/lib/remote_development/README.md) (coding standards, etc.)
* Direction
  * [Workspaces Category Strategy Epic](https://gitlab.com/groups/gitlab-org/-/epics/7419)
  * [Workspaces Category Direction Page](https://about.gitlab.com/direction/create/remote_development/workspaces/)

## Initial Triage

Determine which REST/GraphQL endpoint is affected and the problems that can arise with them from the list below. See [Steps to debug issue](#steps-to-debug-issue) for further debugging according to the issue.

* REST - `POST /api/internal/kubernetes/agent_configuration`
  * GitLab Agent for Kubernetes(agentk) will not be able to fetch its configuration through GitLab Relay (KAS) and would thus fail.
  * Database updates to the workspaces agent configs table will be affected.
* REST - `GET /api/internal/kubernetes/modules/remote_development/prerequisites`
  * The `remote_development` module of the GitLab Agent for Kubernetes(agentk) will not be able start as it requires this information and would thus fail.
* REST - `POST /api/internal/kubernetes/modules/remote_development/reconcile`
  * The `remote_development` module of the GitLab Agent for Kubernetes(agentk) will not be able to send information to Rails about the current state of workspaces in Kubernetes resources nor receive information from Rails about the changes in new/existing workspaces.
* GraphQL - `mutation workspaceCreate`
  * Users will not be able tpo create a new workspace.
* GraphQL - `mutation workspaceUpdate`
  * Users will not be able to change the desired state of an existing workspace.
* GraphQL - `mutation namespaceCreateRemoteDevelopmentClusterAgentMapping`
  * Users will not be able to map/unmap cluster agents in the group settings.
* GraphQL - `query Namespace.remoteDevelopmentClusterAgents`
  * Users will not be able to list the available agents while creating a new workpace.
  * Users will not be able to list the mapped/unmapped cluster agents in the group settings.
* GraphQL - `query CurrentUser.workspaces`
  * Users will not be able to list their workspaces.
* GraphQL - `query projects`
  * Users will not be able to list the projects or get the devfiles for a project while creating a new workpace.

## Dashboards

### Infra overview

* [Workspaces infra index](https://gitlab-com.gitlab.io/gl-infra/platform/stage-groups-index/remote-development.html#workspaces)

### Grafana Dashboards

* [Remote Development Group Grafana Dashboard](https://dashboards.gitlab.net/d/stage-groups-remote_development) (log in via Google before clicking link)

### Logging

* All Workspaces category requests with 500+ HTTP status for last 7 days: [Kibana](https://log.gprd.gitlab.net/app/r/s/nHMla)
* See the `Extra Links` panel in the [Remote Development Group Grafana Dashboard](#grafana-dashboards)

### Sentry

* [Remote Development group Sentry dashboard](https://new-sentry.gitlab.net/organizations/gitlab/issues/?environment=gprd&project=3&query=feature_category%3Aworkspaces+is%3Aunresolved&referrer=issue-list&statsPeriod=7d)
* See the `Extra Links` panel in the [Remote Development Group Grafana Dashboard](#grafana-dashboards)

### Tableau

NOTE: This source of information is for historic data, but is not updated in real time.

* [Tableau Workspaces metrics dashboard](https://10az.online.tableau.com/#/site/gitlab/views/EditorMetrics/WorkspacesDashboard?:iid=1)

## Steps to debug issue

### If GitLab Agent for Kubernetes(agentk) configuration are not reflected during workspace creation

* Check if the [agent configuration file](https://docs.gitlab.com/user/clusters/agent/work_with_agent/#configure-your-agent) is validating validating it against [workspaces related settings](https://docs.gitlab.com/user/workspace/settings/). Any error in the agent configuration is not surfaced in the UI. If there is an error, it will not be persisted in the database as well.
  * [Command to get raw agent configuration stored in the project files](#get-raw-agent-configuration-stored-in-the-project-files).
  * [Command to validate agent config](#validate-the-workspaces-agent-config).
* Check if the [agentk is connected to GitLab](https://docs.gitlab.com/user/clusters/agent/work_with_agent/#view-your-agents). Validate the associated configuration file.
  * [Command to get cluster agent](#get-the-cluster-agent).
  * [Command to validate agent config](#validate-the-workspaces-agent-config).
* Check if GitLab Relay (KAS) is available.

### If GitLab Agent for Kubernetes(agentk) is not visible during workspace creation

* Check if the [GitLab Agent for Kubernetes(agentk) has been mapped at any parent group of the project from which workspace is being created](https://docs.gitlab.com/user/workspace/gitlab_agent_configuration/#allow-a-cluster-agent-for-workspaces-in-a-group).
  * [Command to get the mappings of cluster agent for a group](#get-the-mappings-of-cluster-agent-for-a-group).
* Check if the [agent configuration file](https://docs.gitlab.com/user/clusters/agent/work_with_agent/#configure-your-agent) is valid by validating it against [workspaces related settings](https://docs.gitlab.com/user/workspace/settings/). Any error in the agent configuration is not surfaced in the UI. If there is an error, it will not be persisted in the database as well.
  * [Command to get raw agent configuration stored in the project files](#get-raw-agent-configuration-stored-in-the-project-files).
  * [Command to validate agent config](#validate-the-workspaces-agent-config).

### If devfile is not visible during workspace creation

* Check if [devfile is present at the right location in the project](https://docs.gitlab.com/user/workspace/#custom-devfile).

### If workspace creation fails due to error in devfile

* Check the [devfile is valid](https://docs.gitlab.com/user/workspace/#validation-rules). Validate it against the [devfile schema](https://devfile.io/docs/2.3.0/devfile-schema) if needed(select the appropriate schema version).

### If workspace is stuck in starting state

This cannot be debugged unless you have access to the underlying Kuberenetes cluster.

* Wait for 10 minutes.
* Check the details of the underlying workspace pod.
* Check the logs of the underlying workspace pod.

### If workspace is stuck in failed state

This cannot be debugged unless you have access to the underlying Kuberenetes cluster.

* Check the details of the underlying workspace pod.
* Check the logs of the underlying workspace pod.
* Check if the cloning of the project succeeded.
* Check if the tools(e.g. SSHD, GitLab VS Code fork for Workspaces) are copied to the workspace.
* Check if the tools started correctly.
* Check if any of the container of the workspace pod are restarting.
* Check if the underlying Kubernetes persistent volume was created successfully.

### If workspace will not start or stop or restart or terminate

* Check if the GitLab Agent for Kubernetes(agentk) configuration has `remote_development.enabled` set to `true`.
* Check if the GitLab Agent for Kubernetes(agentk) is connected.
* Check if the GitLab Agent for Kubernetes(agentk) is running in Kubernetes.
* Check if GitLab Relay (KAS) is available.

### If the extensions marketplace is not available in workspace

The extensions marketplaces settings are inherited from WebIDE settings.

* Check if [extensions marketplace is enabled by the GitLab admin](https://docs.gitlab.com/administration/settings/vscode_extension_marketplace/#enable-with-default-extension-registry).
* Check if the [extension marketplace is enabled in your user preferences](https://docs.gitlab.com/user/profile/preferences/#integrate-with-the-extension-marketplace).

Any changes to the above settings will only be reflected in new workspaces.

### If extenion is not available in extensions marketplace

The default extensions marketplace used is OpenVSX. The user can configure their [custom extensions marketplace](https://docs.gitlab.com/administration/settings/vscode_extension_marketplace/#customize-extension-registry).

* Check if the extension is available on [OpenVSX](https://open-vsx.org/) or on the custom marketplace set by the user. There can be extensions which are available on the official [VS Code extensions marketplace](https://marketplace.visualstudio.com/vscode) which are not available other extensions marketplace. This is controlled by the extension author.
* Check if the extension works in a remote environment. There are many extensions which only work on desktop or only on browser but not on remote.

### If AI capabilities are not available in workspace

* Check if the licenses are properly set.

## Debugging Commands

### Get the cluster agent

```ruby
cluster_agent_id = 1
cluster_agent = Clusters::Agent.find(cluster_agent_id)
```

### Get the workspaces agent config for a cluster agent

```ruby
cluster_agent_id = 1
workspace_agent_config = RemoteDevelopment::WorkspacesAgentConfig.find_by(cluster_agent_id: cluster_agent_id)
```

### Get workspaces for a cluster agent

```ruby
cluster_agent_id = 1
cluster_agent = Clusters::Agent.find(cluster_agent_id)
workspaces = cluster_agent.workspaces
```

### Get workspaces agent config for a workspace

```ruby
workspace_id = 1
workspace = RemoteDevelopment::Workspace.find(workspace_id)
workspace_agent_config = workspace.workspace_agent_config
```

### Get workspaces variables for a workspace

```ruby
workspace_id = 1
workspace = RemoteDevelopment::Workspace.find(workspace_id)
workspace_variables = workspace.workspace_variables
```

```ruby
workspace_id = 1
workspace_variables = RemoteDevelopment::WorkspaceVariable.find_by(workspace_id: workspace_id)
```

### Validate the workspaces agent config

```ruby
workspace_agent_config = RemoteDevelopment::WorkspacesAgentConfig.new
workspace_agent_config.enabled = "invalid_value"
workspace_agent_config.valid?
workspace_agent_config.errors
```

### Get raw agent configuration stored in the project files

See [search_projects.query.graphql](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/assets/javascripts/workspaces/user/graphql/queries/search_projects.query.graphql).

### Get the mappings of cluster agent for a group

See [get_agents_with_mapping_status.query.graphql](https://gitlab.com/gitlab-org/gitlab/blob/master/ee/app/assets/javascripts/workspaces/agent_mapping/graphql/queries/get_agents_with_mapping_status.query.graphql).
