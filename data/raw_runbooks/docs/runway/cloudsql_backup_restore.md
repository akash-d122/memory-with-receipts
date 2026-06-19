# Restore/Backup Runway-managed Cloud SQL

This document is meant for (1) disaster-recovery purposes or (2) change management issues with high risk of data corruption/loss (e.g. snapshot migration from an external Cloud SQL instance).

## Backup

All Runway-managed Cloud SQL instances will have periodic backups. These backups are tested daily
through [restore and data validation jobs](https://docs.runway.gitlab.com/managed_services/cloudsql/#restore-validation-1).

Service owners may want to manually create a backup before performing a critical data migration.
They may do so using a change management issue and enlisting the help from SREs.

[Creating manual backup](https://cloud.google.com/sql/docs/postgres/backup-recovery/backing-up#on-demand)

```
gcloud sql backups create --async --project PROJECT_NAME --instance=INSTANCE_NAME --description="<insert description here>"
```

[Listing existing backups](https://cloud.google.com/sql/docs/postgres/backup-recovery/backing-up#viewbackups)

```
gcloud sql backups list --project PROJECT_NAME --instance INSTANCE_NAME
```

[Listing backups during outages](https://cloud.google.com/sql/docs/mysql/backup-recovery/backing-up#backuplist)

During an outage, you can only view backups for that instance using a wildcard (-) and grep for the instance.

```
gcloud sql backups list --project PROJECT_NAME --instance - | grep INSTANCE_NAME
```

## Restore

`BACKUP_ID` can be retrieved by listing the available backups. Restoring operations should be performed through a change management issue and approved by the engineer-on-call.

NOTE: Restoring from a backup means data changes between the time of backup and time of restore will be lost. Only perform restore operations if absolutely necessary.

```
gcloud sql backups restore BACKUP_ID --project PROJECT_NAME --restore-instance=INSTANCE_NAME
```
