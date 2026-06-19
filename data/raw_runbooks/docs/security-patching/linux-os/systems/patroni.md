# Patroni

## Overview

Our [Patroni](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/patroni) deployments are responsible for providing PostgresQL database clusters for GitLab.com.

These clusters are highly available, deployed in a single leader, multiple replica topology. Individual read replicas can be taken offline for patching with minimal impact to the running application. In order to perform maintenance on the leader node, one of the replicas must first be promoted to leader to avoid impact to the application.

[Discussion issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/25663)

## System Identification

Knife query:

```
knife search node 'roles:gprd-base-db-patroni*' -i | sort
```

As of writing (08/2024) the clusters we run in GPRD are:

1. main
1. ci
1. registry

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

For each cluster that we run, we will perform the upgrade on one node at a time.

- Ensure the current node is not the leader:
  - `sudo gitlab-patronictl list`
  - If performing maintenance on the current Leader, use (or refer to) the [Switchover Patroni Leader](https://gitlab.com/gitlab-com/gl-infra/db-migration/-/tree/master/dbre-toolkit?ref_type=heads) ansible Playbook to accomplish this.
    - [Additional documentation may be needed](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/7674#note_2078428873) around setup steps before running the playbook.
- Set the node into maintenance mode:
  - `knife node run_list add <node name> 'role[<env>-base-db-patroni-maintenance]'`
- Run chef-client on the host. Confirm the node has the `noloadbalance` and `nofailover` tags.
- Perform patching via Apt
- Reboot
- Wait for the replica to get back on-line and in sync (it can take several minutes to resync depending on how long it took for the node to restart)
  - Check the node lag with `sudo gitlab-patronictl list`
- Remove the Replica from maintenance mode
  - `knife node run_list remove <node name> 'role[<env>-base-db-patroni-maintenance]'`
- Run chef-client on the host. Confirm the node do NOT HAVE `noloadbalance` tag (some nodes might still have `nofailover`, and each cluster backup node, usually node 02, will also continue with `noloadbalance`).
  - Check pgbouncer metrics to observe if the replica is back to the RO load balance;
- Repeat for the remaining nodes in the cluster

## Additional Automation Tooling

None currently exists.

The is an [open issue](https://gitlab.com/gitlab-com/gl-infra/dbre/-/issues/31) aimed at automating these sorts of tasks.
