# Postgres Replicas

## Overview

Besides our Patroni-managed databases we also have 4 single Postgresql instances
for disaster recovery and WAL archive testing purposes:

- gprd:
  - postgres-ci-dr-archive-2004-01-db-gprd.c.gitlab-production.internal
  - postgres-ci-dr-delayed-2004-01-db-gprd.c.gitlab-production.internal
  - postgres-dr-main-archive-2004-01-db-gprd.c.gitlab-production.internal
  - postgres-dr-main-delayed-2004-01-db-gprd.c.gitlab-production.internal
- gstg:
  - postgres-ci-dr-archive-2004-01-db-gstg.c.gitlab-staging-1.internal
  - postgres-ci-dr-delayed-2004-01-db-gstg.c.gitlab-staging-1.internal
  - postgres-dr-archive-2004-01-db-gstg.c.gitlab-staging-1.internal
  - postgres-dr-delayed-2004-01-db-gstg.c.gitlab-staging-1.internal

Archive and delayed replica both are replaying WAL archive files from GCS via
wal-g which are sent to GCS by the Patroni primary (with a [retention
policy](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/google/database-backup-bucket/-/merge_requests/10)
sending them to coldling storage after 1 week and deletion after 90 days).
The delayed replica though is replaying them with an 8 hour delay, so we are
able to retrieve deleted objects from there within 8h after deletion if needed.

The archive replica is also used for long-running queries for business
intelligence purposes, which would be problematic to run on the patroni cluster.

The "dr" in the name often was leading to confusion with the also existing DR
environment (which isn't existing anymore and which those DBs never belonged
to).

## Setup

Both instances are setup using terraform and Chef:

- [gprd-base-db-postgres-ci-archive-2004 role](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-db-postgres-ci-archive-2004.json)
- [gprd-base-db-postgres-ci-delayed-2004 role](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-db-postgres-ci-delayed-2004.json)
- [gprd-base-db-postgres-main-archive-2004 role](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-db-postgres-main-archive-2004.json)
- [gprd-base-db-postgres-main-delayed-2004 role](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-db-postgres-main-delayed-2004.json)

They use the postgresql version coming with omnibus.

### Setup Replication

While most configuration is already done by Chef, the initial replication needs
to be setup manually. This needs to be done when re-creating the node or if
replication is broken for some reason (e.g. diverged timeline WAL segments in
GCS after a primary failover or for a major postgres version upgrade).

There are 2 ways to (re-)start replication:

- Using wal-g to fetch a base-backup from GCS (easy and works in all cases, but slow)
- Using a disk snapshot from the dr replica before replication broke (faster,
  but a bit more involved and mostly applicable for diverged timelines after a
  failover). You also could take a snapshot from a patroni node, but then you
  need to move PGDATA from `.../dataXX` to `.../data` manually.

#### Pre-requisites

Make sure the postgresql version on this node is compatible with the patroni
one. Else you need to upgrade the gitlab-ee package to a version that brings a
matching embedded postgresql version.

```
/opt/gitlab/embedded/bin/postgres --version
```

Make sure wal-g is working and able to find the latest base backups:

```
cd /tmp/; sudo -u gitlab-psql /usr/bin/envdir /etc/wal-g.d/env /opt/wal-g/bin/wal-g backup-list | sort
name                                   last_modified        wal_segment_backup_start
base_000000020000492A000000E2_00036848 2020-06-04T13:49:56Z 000000020000492A000000E2
base_000000020000493E0000006D_00000040 2020-06-05T07:42:27Z 000000020000493E0000006D
...
```

*IMPORTANT*: You need to make sure to manually find the lates backup in the list
above and note down the name (bas_...). The modification date is bogus as the
policy moving files to nearline storage is updating the modify date, so you
could end up restoring from a backup from 2 weeks ago by accident. Sort the list
by name to be safe!

The `/var/opt/gitlab/postgresql/data/postgresql.auto.conf` file can be managed by
Chef (via `gitlab-server::postgresql-standby` recipe).

##### postgresql.auto.conf for archive replica

The following Chef attributes are used for the archive replica:

```
{
  "gitlab-server": {
    "postgresql-standby": {
      "postgres-conf-auto-rules": {
        "restore_command": "/usr/bin/envdir /etc/wal-g.d/env /opt/wal-g/bin/wal-g wal-fetch \"%f\" \"%p\"",
        "recovery_target_timeline": "latest"
      }
    }
  }
}
```

##### postgresql.auto.conf for delayed replica

The following Chef attributes are used for the delayed replica:

```
{
  "gitlab-server": {
    "postgresql-standby": {
      "postgres-conf-auto-rules": {
        "restore_command": "/usr/bin/envdir /etc/wal-g.d/env /opt/wal-g/bin/wal-g wal-fetch \"%f\" \"%p\"",
        "recovery_target_timeline": "latest",
        "recovery_min_apply_delay": "8h"
      }
    }
  }
}
```

#### Restoring with WAL-G

We will delete the content of the existing PGDATA dir and re-fill it using
wal-g. Retrieving the base-backup will take several hours (1.5 - 2 TiB/h -> ~3.5 - 4.5 hours for a 7TiB database) and
then fetching and replaying the necessary WAL files since the base-backup also can
take a few hours, depending on how much time passed since the last base-backup.

IMPORTANT NOTE: If you're doing this because of a failover in the primary DB, there
is *NO* point doing so until there is a new basebackup from the new primary; before that
you'll just restore then re-run the WALs to the failover point at which time the replay
will fail again in exactly the same manner.  The primary base backups occur at/around midnight UTC,
and (currently) take about 9 hrs (mileage-may-vary)

- `chef-client-disable <comment or link to issue>`
- `gitlab-ctl stop postgresql`
- Clean up the current PGDATA: `rm -rf /var/opt/gitlab/postgresql/data/*`
- Run backup-fetch **in a tmux** as it will take hours:
  - `BASE=<base_000... from backup-list above>`
  - `cd /tmp/; sudo -u gitlab-psql /usr/bin/envdir /etc/wal-g.d/env /opt/wal-g/bin/wal-g backup-fetch /var/opt/gitlab/postgresql/data/ $BASE`
- Converge Chef to create `postgresql.auto.conf` and `standby.signal`: `sudo /opt/chef/bin/chef-client`
- run `gitlab-ctl reconfigure`; this will generate a new postgresql.conf, but will
  probably then fail trying to connect to the newly started up (but still not recovered)
  DB, to create users (or some such).
  [This is fine](https://i.kym-cdn.com/photos/images/newsfeed/000/962/640/658.png)
- chef should have started postgresql, but check with `gitlab-ctl status postgresql`, and
  if necessary, `gitlab-ctl start postgresql`
- check logs in `/var/log/gitlab/postgresql/current` - postgres should be in
  startup first and then start replaying WAL files all the time
- Once postgres is accepting connections again (many hours, but before it gets fully
  up to date, based on some internal determination by postgres), run `gitlab-ctl reconfigure`
  again to ensure it completes any configuration, and will be clean in future.
- `chef-client-enable`

#### Restoring with a disk-snapshot

This is faster than downloading a base-backup first (at least for gprd - for
gstg downloading a base-backup takes around half an hour). We will create a new
disk from the latest data disk snapshot of the postgres dr instance and mount it
in place of the existing data disk and then start WAL fetching.

- Get the config of the current data disk:

```sh
set -x
env="gprd"
project="gitlab-production"
instance="postgres-dr-archive-01-db-gprd"  # adjust for the instance you're working on
disk_name="${instance}-data"
zone=$(gcloud compute disks list --filter="name: $disk_name" --format=json | jq -r 'first | .zone | split("/") | last')
labels=$(gcloud compute disks list --filter="name: $disk_name" --format=json | jq -r 'first | .labels | to_entries | map("\(.key)=\(.value)") | join(",")')
set +x
```

- If you're wanting to use a snapshot from the DR replica before replication broke:

    ```sh
    gcloud compute snapshots list --filter="sourceDisk~$disk_name" --sort-by=creationTimestamp --format=json | jq -r '.[-1]'
    snapshot_name=<name of most recent snapshot from the previous command>
    ```

- Alternatively, if you're using a snapshot from a Patroni host, follow these instructions:

    1. Get the snapshot list matching the data disk of the designated backup replica for the Patroni cluster. For example:

        ```sh
        gcloud compute snapshots list --filter="sourceDisk~<designated backup replica>-db-gprd-data" --sort-by=creationTimestamp --format=json | jq -r '.[-1]'
        snapshot_name=<name of most recent snapshot from the previous command>
        ```

    1. If the most recent snapshot is not recent enough (say <1hr), then you should probably [take a new snapshot](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/patroni/gcs-snapshots.md):

        > **NOTE**: if you're working on a delayed replica, then you probably want a snapshot older than 8 hours (currently - confirm by checking the `recovery_min_apply_delay` setting in the delayed replica Chef role)

        1. SSH to the designated backup replica of the cluster
        1. Run `/usr/local/bin/gcs-snapshot.sh` as the user `gitlab-psql`. Wait for the snapshot to finish.
        1. Get/set the most recent snapshot:

            ```sh
            gcloud compute snapshots list --filter="sourceDisk~<designated backup replica>-db-gprd-data" --sort-by=creationTimestamp --format=json | jq -r '.[-1]'
            snapshot_name=<name of most recent snapshot from the previous command>
            ```

- On the instance you're working on, adjust the `/etc/fstab` entry for the data disk to also make it work for the new disk:

    ```sh
    pd_name="persistent-disk-1"
    pd_path="/dev/disk/by-id/google-${pd_name}"

    if test -L $pd_path; then
        sudo awk -i inplace 'match($0, /\/var\/opt\/gitlab/) { $0 = gensub(/^UUID=[^\ ]+/, "'$pd_path'", 1) } 1 {print $0}' /etc/fstab
        echo "Updated /etc/fstab"
    else
        echo "ERROR - double-check the persistent disk path as '${pd_path}' does not exist"
    fi
    ```

- Exchange the data disk with a new one created from the snapshot:

```sh
# stop the instance
gcloud --project $project compute instances stop $instance --zone $zone

# detach the disk
gcloud --project $project beta compute instances detach-disk $instance --disk $disk_name --zone $zone

# delete the disk
gcloud --project $project beta compute disks delete $disk_name --zone $zone

# create new disk from snapshot (takes some time...)
gcloud --project $project beta compute disks create $disk_name --type pd-ssd --source-snapshot $snapshot_name --labels="$labels" --zone $zone

# attach disk
gcloud --project $project compute instances attach-disk $instance --disk $disk_name --device-name $pd_name --zone $zone

# start instance
gcloud --project $project compute instances start $instance --zone $zone
```

- If you're using a snapshot from a Patroni host, then SSH to `$instance` and do the following:

    1. Ensure Postgres is not running:

        ```sh
        gitlab-ctl stop postgresql
        ```

    1. Rename data dir and remove dirs you don't need:

        ```sh
        cd /var/opt/gitlab/postgresql
        mv data* data
        cd ..
        rm -rf pgbouncer patroni
        ```

    1. Fix permissions:

        ```sh
        chown -R gitlab-psql:gitlab-psql postgresql
        chgrp root postgresql
        ```

    1. Reconfigure/start Postgres:

        ```sh
        gitlab-ctl reconfigure postgresql
        ```

        This step should start Postgres and start recovering. It'll ultimately fail as it tries to talk to the DB and the DB is recovering. Try again once it has finished
        recovering (could take minutes/hours depending on how many WALs it has to catch up on)

        Keep an eye on the CSV log (in `/var/log/gitlab/postgresql`) for a `restartpoint complete` message.

    1. Run the reconfigure step again:

        ```sh
        gitlab-ctl reconfigure postgresql
        ```

      It should run quickly and finish gracefully.

    1. Restart Postgres for good measure (maybe a new version of Postgres was installed as a result of the reconfigure):

      ```sh
      gitlab-ctl restart postgresql
      ```

- Check there is no terraform plan diff for the archival replicas. Run the
  following for the matching environment:

    ```sh
    tf plan -out plan -target module.postgres-dr-archive -target module.postgres-dr-delayed
    ```

 If there is a plan diff for mutable things like labels, apply it. If there is
 a plan diff for more severe things like disk name, you might have made a
 mistake and will have to repeat this whole procedure.

## Check Replication Lag

[Thanos](https://thanos.gitlab.net/graph?g0.range_input=1h&g0.max_source_resolution=0s&g0.expr=pg_replication_lag%7Benv%3D%22gprd%22%2C%20fqdn%3D~%22postgres-dr.*%22%7D&g0.tab=0)

## Pause Replay on Delayed Replica

If we want to restore content that was changed/deleted less than 8h before on
our Patroni cluster, we can do it on the delayed replica, because it is
replaying the WAL files with an 8h delay. To prevent reaching the 8h limit, we
can temporarily pause the replay:

- eventually silence replication lag alerts first
- ssh to the delayed replica
- `systemctl stop chef-client`
- `gitlab-psql -c 'SELECT pg_xlog_replay_pause();'`
- extract the data you need...
- `gitlab-psql -c 'SELECT pg_xlog_replay_resume();'`
- `systemctl start chef-client`

Also see the [deleted-project-restore runbook](../uncategorized/deleted-project-restore.md).

## Start, stop and check status of PostgreSQL

Archive and delayed replicas manage their PostgreSQL instance with the `gitlab-ctl` command. Chef-client should start PostgreSQL automatically, but in case it doesn't you can use the following commands:

- Check PostgreSQL Status:

```
gitlab-ctl status postgresql
```

- Start PostgreSQL:

```
gitlab-ctl start postgresql
```

- Stop PostgreSQL

```
gitlab-ctl stop postgresql
```
