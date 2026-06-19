# ClickHouse Cloud Failure Remediation, Backup & Restore Process

Follow this runbook when a ClickHouse Cloud database is broken beyond repair and requires remediation.

## Check metrics

Check the metrics of the failed instance. Can the issue be mitigated in the first instance by increasing the available memory?

* `https://clickhouse.cloud/service/ad02dd6a-1dde-4f8f-858d-37462fd06058` shows available metrics.
* Speak to a ClickHouse Cloud administrator to attempt this (`#f_clickhouse`).

## Speak to ClickHouse Cloud support

1. In the first instance, open a P1 support ticket in [ClickHouse Cloud](https://clickhouse.cloud).
1. Ping the team in `#f_clickhouse` to make them aware of the failure.
1. Consider pinging ClickHouse team members in `clickhouse-gitlab-external431` to expedite the request.

## Restoring from Backup

> Only ClickHouse Cloud administrators are permitted to do this.

1. Create a new Admin API key - <https://clickhouse.cloud/organizations/8a0d56e3-d8f0-4e70-80bf-a8bf6ee950bd/keys>
    * Set an expiration of 1 hour.
1. Use `cURL` to list all clusters:

    ```sh
    curl -u '{API KEY}:{API SECRET}' \
        "https://api.clickhouse.cloud/v1/organizations/8a0d56e3-d8f0-4e70-80bf-a8bf6ee950bd/services"
    ```

1. Find the cluster in question and list its backups:

    ```sh
    curl -u '{API_KEY}:{API SECRET}' \
        "https://api.clickhouse.cloud/v1/organizations/8a0d56e3-d8f0-4e70-80bf-a8bf6ee950bd/services/bf5e7003-585d-4767-84ed-13fe3b934c8d/backups"
   ```

1. Create a new service _from the backup_ - make sure to note the password in the response, it will only be available once. This should take around 5-10 minutes but relies on GCP:

    ```shell
    curl -X "POST" "https://api.clickhouse.cloud/v1/organizations/8a0d56e3-d8f0-4e70-80bf-a8bf6ee950bd/services" \
         -H 'Content-Type: application/json' \
         -u '{API KEY}:{API SECRET}' \
         -d $'{
      "tier": "production",
      "provider": "gcp",
      "region": "us-central1",
      "name": "restored-gitlab-com-production-TEST", # This should be the same name as the existing service, prefixed with 'restored'.
      "idleScaling": false,
      "backupId": "REPLACE ME" # This is the backup ID from step 3.
    }'
    ```

1. Enable a private connection to the instance using the self-serve information: `https://clickhouse.com/docs/en/manage/security/gcp-private-service-connect#add-endpoint-id-to-services-allow-list`
1. Update the secrets and connection strings in [Vault](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/0f51795585cd087b5db5d1b16f89a0dd875f8215/releases/gitlab-external-secrets/values/gprd.yaml.gotmpl#L392) to connect to the new instance. Then update the connection string at [this location](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/0f51795585cd087b5db5d1b16f89a0dd875f8215/releases/gitlab/values/gprd.yaml.gotmpl?page=3#L2008)
1. Redeploy the latest version of the stack.
1. Check the following on the [main team dashboard](https://dashboards.gitlab.net/d/thEkJB_Mz/clickhouse-cloud-dashboard?orgId=1):
   * ClickHouse is still writing new data.
