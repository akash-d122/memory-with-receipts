# Debugging Patches

This guide covers the workflow for determining if a patch has failed and why, helping you debug patch issues efficiently.

## Checking Patch Status

View all patches and their statuses:

```bash
ringctl patch ls -e <cellsdev|cellsprod>
```

Get detailed information about a specific patch, including pipeline status and commit history:

```bash
ringctl patch get <patch_id> -e <cellsdev|cellsprod>
```

This command displays:

- Latest commit information and timestamp
- Current pipeline status for in-rollout patches
- Links to the deployment pipeline for in-rollout and failed patches
- Link to the complete commit history for the patch

## Understanding Patch States

Patches can be in one of the following states:

- **Pending**: The patch is waiting for previous patches in the queue to finish
- **In Rollout**: The patch is currently being applied to rings
- **Failed**: The patch application failed at a specific ring
- **Completed**: The patch has been successfully applied to all rings

## Investigating Failed Patches

When a patch is in the `failed` state, follow these steps to investigate:

1. **Check the patch details**

   Review the detailed information of the specific patch (as shown in [Checking Patch Status](#checking-patch-status)).

1. **Review the failed pipeline**

   Click on the pipeline link from the output above. The pipeline will show which stage failed.

1. **Examine the commit history**

   Use the commit history link from the output above.

   This shows all commits related to your patch, including:
   - The initial patch creation
   - Commits applying the patch to each ring
   - Any retry attempts

1. **Check the job logs**

   In the failed pipeline, click on the failed job to view its logs. Common failure causes include:
   - Deployment timeouts
   - Resource conflicts
   - Invalid configuration values
   - Infrastructure issues

1. **Determine next steps**

   Based on the failure cause:
   - **Transient failures** (runner system failures, timeouts): [Retry the patch](retrying.md)
   - **Configuration errors**: [Delete the patch](deleting.md) and create a new one with the correct values
   - **Migration failures**: Check the migration logs to identify the issue.
      As a last resort, you may need to [connect to the toolbox pod](../toolbox.md) to manually execute migrations
   - **Infrastructure issues**: Open an issue to investigate the underlying problem before retrying

## Investigating Pending Patches

If a patch has been in the `pending` state longer than expected:

1. **Check the patch queue**

   Review the patch list (as shown in [Checking Patch Status](#checking-patch-status)) and look for patches that are ahead in the queue.
   If there are other patches ahead in the queue, those need to complete first before your patch will be applied.

1. **Verify patch processing hasn't halted**

   Check if there are any patches currently `in rollout`.

   - **If a patch is in rollout**:
      - Verify the patch's pipeline is running successfully by checking its status with `ringctl patch get <patch_id>`.
      - If the pipeline has failed, patch processing has stopped. Investigate and resolve the failed patch first.
      - If the pipeline is running, monitor the patch to ensure it's not taking longer than expected.

   - **If no patches are in rollout and there are pending patches**:
      - Patch processing may have stopped. Review the [tissue pipelines page] to see if there are any stuck or failed pipelines.

   [tissue pipelines page]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/pipelines

## Accessing Cells Logs

### For GCP Cells

- Follow the [breakglass access guide](../breakglass.md#project-access) to get access with the console and view the cell's logs on the `Log Explorer`

### For AWS Cells

Logs can be accessed for each Cell using the following links:

- Grafana: grafana.<managed_domain>
- OpenSearch: opensearch.<managed_domain>

> [!note]
>
> - The `managed_domain` value can be found in the cell's tenant model in rings/<AMP_ENVIRONMENT>/<RING_NUMBER> folder in [Tissue]
> - The password to access both the Grafana and OpenSearch are found in the Secrets Manager of the tenant's AWS account
>   - Grafana: `gitlab/dedicated/tenants/<TENANT_ID>/grafana` for `admin` user
>   - OpenSearch: `gitlab/dedicated/tenants/<TENANT_ID>/opensearch_master` for `master` user

[Tissue]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue
