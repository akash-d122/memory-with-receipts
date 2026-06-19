# HAProxy

## Overview

HAProxy serves as the entrypoint for most of our applications, and runs with many replicas. Assuming there will be sufficient capacity in the fleet while individual nodes are taken offline for maintenance, there should be minimal, or no disruption from the patching of these systems.

## Lead Time

Traffic patterns should be evaluated and a time as soon as possible could be chosen when it is believed that there will be sufficient capacity in the fleet that is not offline for maintenance at a given time.

## System Identification

We run multiple HAProxy fleets in GPRD, with each one handling a portion of the traffic for GitLab.com. The following `knife` query can be used to identify these systems.

```
knife search node 'roles:gprd-base-haproxy*' -i  | sort
```

The following distinct fleets currently exist:

- main
- ci
- pages
- registry

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

Updates for each HAProxy fleet will be performed in groups, the size of the group will be determined by the total number of nodes in a fleet, and current level of traffic.

- HAProxy will be shut down on the nodes being upgraded
  - A drain script is automatically called to shun health check connections as part of the Systemd unit, so the nodes will be removed from the load balancing pools.
- Packages will be updated via Apt.
- Instances will be rebooted onto new kernel versions.
  - Health checks will resume working on boot, and the nodes will start accepting connections from the GCP load balancer.
- Repeat for each group.

## Additional Automation Tooling

Pipelines exist in the [`patch-automation`](https://ops.gitlab.net/gitlab-com/gl-infra/ops-team/toolkit/patch-automation) project that can be initiated manually to patch this fleet.
