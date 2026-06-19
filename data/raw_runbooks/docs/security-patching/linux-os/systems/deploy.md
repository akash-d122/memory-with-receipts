# Deploy

## Overview

The "deploy" fleet runs the rails application and is used to facilitate execution of deployment related tasks such as database migrations. These nodes do not handle customer facing traffic, however, are required by the deployment pipelines.

## Lead Time

Lead time for patching these systems should be minimal, as long as the time is agreed upon with release managers. Deployments will need to be blocked for the duration of the maintenance.

## System Identification

Knife query to locate relevant systems:

```
knife search node 'role:gprd-base-deploy-node*' -i
```

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

- Notify release managers that deployments will need to be paused.
- Block deployments with a C2 change issue and appropriate labels.
- Update apt packages and reboot the nodes.
- Remove deployment blocks by closing the change issue.

### Ideal Commands

- `sudo apt-mark hold gitlab-ee`
- `sudo apt update`
- `sudo apt upgrade --yes`
- `sudo apt-mark unhold gitlab-ee`
- `sudo reboot`

## Additional Automation Tooling

None currently exists
