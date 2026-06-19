# Gitaly

## Overview

Gitaly currently is deployed in a way that makes each individual server a single point of failure (SPoF) for GitLab.com.

Because of this, the service requires substantial coordination when scheduling reboots.

Work on the [Gitaly raft](https://gitlab.com/groups/gitlab-org/-/epics/8903) implementation may make maintenance considerably easier by removing it as a SPoF, and possibly enabling the migration to Kubernetes.

[Discussion issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/25667)

## Lead Time

Lead time for performing patching will likely be substantial. Coordination must be done with Customer Support teams, as well as possibly account managers for larger customers before scheduling an outage period for git operations on GitLab.com.

## Required Time For Execution

This is largely going to depend on how many Gitaly nodes we upgrade at once. If we do a single instance at a time, you could expect the maintenance window to be a little more than 5 hours. _~160 nodes * 2 minutes per reboot cycle_

We could make the decision to increase the number of nodes upgraded at once to reduce the overall time, but accept that the likelihood of impact to any given user would be higher for the shorter duration.

## System Identification

Knife query:

```
knife search node 'roles:gprd-base-stor'
```

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

Run against instances in a rolling fashion, in a predetermined group size

- Disable the [weight assigner](https://ops.gitlab.net/gitlab-com/gl-infra/gitaly-shard-weights-assigner) before starting.
- Set the weight for new projects on the storage(s) to zero
- Update packages with apt
- Reboot instance
- Validate that Gitaly is running again.
  - `gitlab-ctl status`
  - Check the log (/var/log/gitlab/gitaly/current) to ensure that startup errors haven't occurred.
- Restore the weight on the storage to the previous value.
- Repeat for each node
- Enable the weight assigner

## Additional Automation Tooling

None currently exists.
