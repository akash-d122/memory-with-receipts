# Runner Managers

## Overview

The Runner Manager fleet are responsible for creating ephemeral runners used to carry out CI jobs for GitLab.com.

The Runner Manager fleet uses a blue/green deployment strategy that can be leveraged to apply security patches to the set of instances that are not currently active without disruption to service.

## Lead Time

Because there should always be an inactive set of runner instances, there should be minimal lead time required to begin patching these systems.

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

See the `Additional Automated Tooling` section below for how to execute the runner specific patching process on a given shard.

We will take advantage of the Runner Manager's blue/green deployment to apply patches to the currently inactive color, make them active, then apply patches to the color that was removed from active service.

- Identify the currently inactive color
  - Select the current shard on the [ci-runners: Deployment overview](https://dashboards.gitlab.net/d/ci-runners-deployment/ci-runners3a-deployment-overview?orgId=1) dashboard. The ***active*** color will appear in the deployment column of the `GitLab Runner Versions` panel.
- Initiate package updates across these nodes.
- Reboot
- Perform a deployment to make this color active.
- Wait for the now-inactive color to completely drain.
  - You can use this [Prometheus query](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22wm9%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22sum%28gitlab_runner_jobs%29%20by%20%28deployment,%20shard%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-gprd%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1) to help determine when the inactive color of a given shard is no longer processing jobs.
- Patch and reboot these instances.

### CI COS runner images

The OS images deployed for ephemeral runner VMs is statically defined via Chef roles in chef-repo. [Example](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/169ae54f6837a70751455b216fd18d9cafd3c774/roles/runners-manager-private.json#L90).
Updating these Chef attributes will change the deployed image used by the ephemeral runners for a given shard.

## Additional Automation Tooling

There is a Slack command that can be executed from the `#production` Slack channel to initiate patching of the individual runner shards. To use this:

1. Identify the shard and inactive color you want to patch.
1. In the `#production` Slack channel:
    1. Issue command: `/runner run system-patch-dry-run <shard> <color>`
    1. Verify the upgraded package lists don't contain anything unexpected.
    1. Issue command: `/runner run system-patch <shard> <color>`
