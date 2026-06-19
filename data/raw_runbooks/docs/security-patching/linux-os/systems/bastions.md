# Bastions

## Overview

The Bastion hosts are SSH proxy instances that serve the purpose of allowing connections to internal systems from the internet.

## Lead Time

These instances are stateless and multiple instances are behind GCP load balancers, as such they can be updated at will with little or no lead time.

## System Identification

Knife query:

```
knife search node 'roles:gprd-base-bastion' -i
```

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

- The nodes are upgraded one at a time
- Each node will be removed from it's GCP load balancer by halting the NGINX service running on the host
- Packages will be updated via Apt.
- The instance will be rebooted onto it's new kernel version.
- The node will be added back to the GCP loadbalancers.
- Repeat for each node.

## Additional Automation Tooling

Pipelines exist in the [`patch-automation`](https://ops.gitlab.net/gitlab-com/gl-infra/ops-team/toolkit/patch-automation) project that can be initiated manually to patch this fleet.
