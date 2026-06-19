## Summary

This contains the relevant information for Disaster Recovery on GitLab.com as it relates to testing, validation, and current gaps that would prevent recovery.

[GitLab backups](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/production/#backups) are designed to be tolerant for both zonal and regional outages by storing data in global (multi-region) object storage.

The [DR strategy](https://internal-handbook.gitlab.io/handbook/engineering/disaster-recovery/) for SaaS is based on our current backup strategy:

- [Postgresql backups using WAL-G](/docs/patroni/postgresql-backups-wale-walg.md)
- [GCP disk snapshots](/docs/disaster-recovery/gcp-snapshots.md)

Validation of restores happen in CI pipelines for both the Postgresql database and disk snapshots:

- [Postgresql restore testing](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/database/disaster_recovery.html#restore-testing)
- [GitLab production snapshot restores](https://gitlab.com/gitlab-com/gl-infra/gitlab-restore/gitlab-production-snapshots)

## Recovery Guide

If you suspect there is a regional or zonal outage (or degredation), please read through the [recovery guide](./recovery.md).

## Testing

### Test environment

For testing recovery of snapshots the [`dr-testing`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments/dr-testing) environment can be used, this environment holds examples of different recovery types including Gitaly snapshot recovery.

### Denying network traffic to an availability zone

A helper script is available to help simulate a zonal outage by setting up firewall rules that prevent both ingress and egress traffic, currently this is available to run in our non-prod environments for the zones `us-east1-b` and `us-east1-d`.
The zone `us-east1-c` has [SPOFs like the deploy and console nodes](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/16251#us-east1-c-outage) so we should avoid running tests on this zone until they have been resolved in the [epic tracking critical work related to zonal failures](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/800).

#### Setting firewall rules

**Note**: Run this script with care! All changes should go through [change management](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/), even for non-prod environments!

```
$ ./zone-denier -h
Usage: ./zone-denier [-e <environment> (gstg|pre) -a <action> (deny|allow) -z <zone> -d]

  -e : Environment to target, must be a non-prod env
  -a : deny or allow traffic for the specified zone
  -z : availability zone to target
  -d (optional): run in dry-run mode

Examples:

  # Use the dry-run option to see what infra will be denied
  ./zone-denier -e pre -z us-east1-b -a deny -d

  # Deny both ingress and egress traffic in us-east1-b in PreProd
  ./zone-denier -e pre -z us-east1-b -a deny

  # Revert the deny to allow traffic
  ./zone-denier -e pre -z us-east1-b -a allow
```

The script is configured to exclude a static list of known SPOFs for each environment.
