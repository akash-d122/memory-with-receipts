# Zlonk Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter={type%3D%22zlonk.postgres%22>}
* **Label**: None at this time.
* **Logging**: `/var/log/gitlab/zlonk/<project>/<instance>/zlonk.log`

## Overview

Zlonk creates, prepares for use, and destroys ZFS clones.

In its [first iteration](https://gitlab.com/gitlab-com/gl-infra/zlonk/-/blob/master/bin/zlonk.sh), it is a simple shell script that is customized for _cloned Postgres replicas_. It was initially written to address the [long data extraction outage](https://gitlab.com/gitlab-data/analytics/-/issues/8576) we experienced around March - May 2021. Other uses uses include the generation of ad-hoc replicas for [testing and clean-up purposes](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/4591).

It currently only runs from `cron` on `patroni-v12-zfs-01-db-grpd`.

## Architecture

Zlonk is a simple wrapper to create and destroy clones, and, as such, have very little in the way of "Architecture". However, there are a few concepts useful in understanding what it does and how it works.

### Projects and instances

Zlonk is called with two arguments: a `project` and an `instance`. A project is simply a grouping mechanism for instances. Instances map directly to a ZFS clone. For instance, the Data team uses the `dailyx` instance in the `datalytics` project.

### Zlonk acts like a switch

The current version of Zlonks acts like a switch: when a clone is not present, it creates it (and confifgures a Postgres instance to use it); when it it present, it destroys it (after stopping the cloned Postgres replica).

### ZFS datasets and file systems

The `zpool0/pg_datasets/data12` dataset is under Zlonk control. This dataset is mounted as a file system for use by the _cascaded Postgres replica_ under `/var/opt/gitlab/postgresql/data12` much like any other database replica. Clones are created in `zpool0/pg_datasets` and are named with the project and instance.

```
zpool0/pg_datasets/data12
zpool0/pg_datasets/data12:datalytics.dailyx
```

### Operations

Zlonk is invoked as follows (see crontab for examples)

```
bin/zlonk.sh <project> <instance>
```

Once invoked, it will behave in one of two ways:

* If the `project:instance` clone **does not exist**, Zlonk will checkpoint postgres, snapshot the file system, create and mount a clone, and start Postgres, which will attempt recovery. Clones are mounted under  `/var/opt/gitlab/postgresql/zlonk/`. At that point, the cloned replica, which is completely indepdendent of the cascaded replica, will be available on an alternate port.
* If the `project:instance` clone **does exist**, Zlonk will fast-stop the _cloned Postgres instance_ and destroy the clone.

## Performance

There are no performance constraints relevant to Zlonk. However, we do have some timeout monitoring in place to ensure the clone and destruction tasks are executed within reason or fail to complete for some reason.

## Monitoring/Alerting

Zlonk implements [job completion](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/uncategorized/job_completion.md) monitoring. Alerts are funneled to the `#alerts` Slack channel with a S4 severity.

## Troubleshooting

### Clone timeouts

Clone timeouts will generally occur when Postgres is unable to recover the database, which we have [observed once](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/5126) since ZLonk went into operation two months ago.

Alert generated:

* **GitLab job has failed**: The GitLab job "clone" resource "zlonk.<project>.<instance>" has failed.
* Tier: `db`, Type: `zlonk.postgres`

We have not found a root cause, but the solution is to destroy and regenerate the clone, so run `zlonk` twice (see crontab for invocation).
