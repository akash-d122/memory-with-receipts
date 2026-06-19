# Redis

## Overview

Our VM based Redis deployments are managed by three different Chef cookbooks.

- [gitlab-redis](https://gitlab.com/gitlab-cookbooks/gitlab-redis)
- [gitlab-redis-cluster](https://gitlab.com/gitlab-cookbooks/gitlab-redis-cluster)
- [omnibus-gitlab](https://gitlab.com/gitlab-cookbooks/cookbook-omnibus-gitlab)

System patching may be performed on instances deployed by any of these, however, limitations may apply to instances using the omnibus-gitlab cookbook. It is not possible to update the `gitlab-ee` packages deployed on these systems without also updating Redis itself, so any vulnerabilities relating to this may require a migration to a new deployment mechanism using one of the other options.

[Discussion issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/25686)

## Lead Time

Our Redis infrastructure is deployed using highly available deployment topologies that should enable security patching with minimal notice.

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

1. Iterate over all nodes in the shard or deployment.
1. If the node is the primary:
   - Ensure we are able to failover.
   - Perform a failover to promote another node.
   - Validate that failover was successful.
1. Reboot the node.
1. Ensure the node booted, and redis started. Start the redis service if needed.
1. Wait for the redis to configure itself as a replica and catch up with the primary.

Most of the required logic for doing so safely exists in the set of redis reconfigure scripts:

- [`omnibus-redis-reconfigure.sh`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/scripts/omnibus-redis-reconfigure.sh)
- [`redis-reconfigure.sh`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/scripts/redis-reconfigure.sh)
- [`redis-cluster-reconfigure.sh`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/scripts/redis-cluster-reconfigure.sh)

These could be adapted to perform a full reboot instead of just a service restart.

## Additional Automation Tooling

No automation exists for the fleets deployed on virtual machines. The scripts mentioned above could be updated to help remove repetitive tasks that apply to individual servers, but today, each instance must be touched by a SRE.
