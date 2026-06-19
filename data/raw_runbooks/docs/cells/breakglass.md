# Breakglass

We follow the [Principle of Least Privilege](https://csrc.nist.gov/glossary/term/least_privilege) whereby SREs don't have default read/write access to Cells infrastructure.  This helps limit blast radius in case of security
incidents or misconfigurations of running scripts locally to production.

# AWS

For AWS-deployed infrastructure, access is managed through Okta SSO using [Identity Center] for the Web Console and CLI.

## Web Console access

1. Go to <https://gitlab.okta.com/>
1. Click the **AWS Cells `<env>` Org** tile of your choosing (you can bookmark the result URL for future use)
    1. `<env>` can be either `Dev` or `Prod`
1. In the AWS access portal, open **Hub Cells`<env>`** and click **AdministratorAccess**
1. This will log you into the Hub account with an assumed Administrator role
1. On the top right of the AWS console, click the `username @ account-id` dropdown and click on `Switch role`[^1]
    1. ![img](./img/cells-gui-access-switch-role.png)
1. In the displayed form, enter account ID as the value of the `/aws_account_id` field from the tenant model of the Cell.
    1. _Example:_ `373633008521` for [cell c01k21yz9qqajjfn6z]
    1. **Note:** The value of the `/amp_aws_account_id` field should _not_ be used when switching roles.
    1. ![img](./img/cells-switch-role-form.png)
1. Enter `IAM role name` as either `dedicated/GitLabTenantAdminOperatorRole` or `dedicated/runner/GitLabRunnerAdminOperatorRole`
1. After switching roles, select the appropriate region (usually, `us-east-1`) to view the resources inside a Cell's account

## CLI access

The following process is the Cells version of the process for GitLab Dedicated which is outlined in [this guide](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/runbooks/break-glass.md#cli).

1. **Login to Hub account:** - Run `assume-env-local.sh` in the [AMP project]. `AMP_ENVIRONMENT` can be either `cellsdev` or `cellsprod`

   ```bash
   AMP_ENVIRONMENT=<environment>; eval "$(./scripts/assume-env-local.sh "${AMP_ENVIRONMENT}")"
   ```

   This will open a prompt in the browser to sign-in using SSO, select `Confirm and continue` and then `Allow access`.

2. **Assume role:** Run `assume-tenant-admin-operator.sh` to assume `dedicated/GitLabTenantAdminOperatorRole` IAM role in the target tenant account

   ```bash
   eval $(./scripts/assume-tenant-admin-operator.sh <TENANT_AWS_ACCOUNT_ID>)
   ```

   `TENANT_AWS_ACCOUNT_ID` is the value of the `/aws_account_id` tenant model field. _Example:_ `373633008521` for [cell c01k21yz9qqajjfn6z]

   > [!note]
   > Do not use the value of the `/amp_aws_account_id` field in the tenant model. (For [cell c01k21yz9qqajjfn6z], `amp_aws_account_id` field's value is `537566696576`)

1. **Confirm AWS access:** Run `aws sts get-caller-identity` to confirm that you have the right user and role ARN

    ``` shell
    $ aws sts get-caller-identity
    {
        "UserId": "<AWS_USER_ID>:OperatorAccess",
        "Account": "<AWS_ACCOUNT_ID>",
        "Arn": "arn:aws:sts::<AWS_ACCOUNT_ID>:assumed-role/GitLabTenantAdminOperatorRole/OperatorAccess"
    }
    ```

### Kubernetes Cluster Access

Once you have gained access to the Cell, you can update your local kubeconfig with the EKS cluster credentials for `<TENANT_ID>`, using the `aws` CLI.

```bash
aws eks update-kubeconfig --region us-east-1 --name <TENANT_ID>
```

> [!note]
> `TENANT_ID` is the value of the `/tenant_id` tenant model field. _Example:_ `c01k21yz9qqajjfn6z` for [cell c01k21yz9qqajjfn6z]

Once this is done, you will be able to use `kubectl` to get resources inside the Kubernetes cluster.

# GCP

We use [Privileged Access Manager (PAM)][PAM] to provide short lived access to GCP via the console or `gcloud`.

## When to escalate

```mermaid
---
title: PAM access entitlements
---
flowchart TD
    need_access[I need access to Cells]

    is_incident{Are you in
    an incident?}
    is_change_incident{Need changes
    to fix an incident?}
    is_change_normal{Need to
    make changes?}
    is_specific_cell{Do you know which Cell
    you need to look at?}
    is_team_members_available{Are team members
    available?}
    is_change_operational{Do you need to
    make temporary changes
    as part of a CR?}

    iac_change[Make changes through IaC]

    project_read
    project_admin
    project_breakglass
    org_read

    need_access-->is_incident

    is_incident-->|Yes| is_change_incident
    is_change_incident-->|No|project_read
    is_change_incident-->|Yes, need write access to quickly solve incident
    I will sync IaC after|is_team_members_available
    is_team_members_available-->|Yes|project_admin
    is_team_members_available-->|No|project_breakglass

    is_incident-->|No| is_change_normal
    is_change_normal-->|No|is_specific_cell
    is_change_normal-->|Yes|is_change_operational
    is_specific_cell-->|Yes|project_read
    is_specific_cell-->|No|org_read
    is_change_operational-->|Yes|project_admin
    is_change_operational-->|No
    OR
    Yes, but I can make changes through IaC|iac_change
```

## How to escalate

Google provides guides to request access through [the console](https://cloud.google.com/iam/docs/pam-request-temporary-elevated-access#request-grant-console)
and through the [`gcloud` CLI](https://cloud.google.com/iam/docs/pam-request-temporary-elevated-access#request_a_grant_programmatically).

Specific Examples:

- [`org_read`](#org_read)
- [`project_read`](#project_read)
- [`project_admin`](#project_admin)
- [`project_breakglass`](#project_breakglass)
- [amp](#amp)

## Levels of access

### Default Access

By default we give [enough permissions](https://gitlab.com/gitlab-com/gl-infra/cells/tissue/-/blob/702095d2f62f7fc65c3171f87e410432c308987f/terraform/modules/cell-environment/iam.tf) to SREs to view the organization, view projects, and use PAM. For any further action through GCP changes must be made
through IaC or using PAM escalation.

| Cells Dev                                               | Cells Prod                                                      |
|---------------------------------------------------------|-----------------------------------------------------------------|
| ![cells dev overview](./img/cells_dev_org_switcher.png) | ![cells_production_overview](./img/cells_prod_org_switcher.png) |

### Org-wide Access

#### [org_read](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/library/terraform/google-privileged-access-manager/-/blob/346edc2e8c2ecee79b8bf06a23819675d4be644d/predefined-entitlements.tf#L9-L28)

- Get access with `gcloud`:

    ```sh
    # $ORG_ID for dev: `425712905585`
    # $ORG_ID for prod: `1073525295030`
    # $CELL_ENV for dev: `dev`
    # $CELL_ENV for prod: `prod`
    gcloud beta pam grants create \
              --entitlement="org-readonly-entitlement-${CELL_ENV}" \
              --requested-duration="1800s" \
              --justification="$ISSUE_LINK" \
              --location=global \
              --organization="$ORG_ID"
    ```

- Get access with console: [dev](https://console.cloud.google.com/iam-admin/pam/entitlements/my?organizationId=425712905585) | [prod](https://console.cloud.google.com/iam-admin/pam/entitlements/my?organizationId=1073525295030)

This entitlement provides the ability to `list` resources at an org-wide level, but does not provide the ability to `get` details for resources, other than IAM bindings. This is useful for initial
discovery and exploration of the resources available across the org.

### Project Access

#### [project_read](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/library/terraform/google-privileged-access-manager/-/blob/346edc2e8c2ecee79b8bf06a23819675d4be644d/predefined-entitlements.tf#L30-L53)

- Get access with `gcloud`:

    ```sh
    # TENANT_ID: Can be found in the "tenant_id" field in the tenant model in `cells/tissue`.
    # example TENANT_ID="c01j2gdw0zfdafxr6"
    gcloud beta pam grants create \
              --entitlement="gldt-readonly-entitlement-${TENANT_ID}" \
              --requested-duration="1800s" \
              --justification="$ISSUE_LINK" \
              --location=global \
              --project="cell-${TENANT_ID}"
    ```

- Get access with console: [dev](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=cell-c01j2t2v563b55mswz) | [prod](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=cell-c01j2gdw0zfdafxr6)

This entitlement provides the ability to view resources within a project scope. This allows you to `list` and `get` resources to discover and describe specific resource configurations, e.g. Viewing
the details for a GKE cluster and its nodes.

#### [project_admin](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/library/terraform/google-privileged-access-manager/-/blob/346edc2e8c2ecee79b8bf06a23819675d4be644d/predefined-entitlements.tf#L55-L110)

- Get access with `gcloud`:

    ```sh
    # TENANT_ID: Can be found in the "tenant_id" field in the tenant model in `cells/tissue`.
    # example TENANT_ID="c01j2gdw0zfdafxr6"
    gcloud beta pam grants create \
              --entitlement="gldt-admin-entitlement-${TENANT_ID}" \
              --requested-duration="1800s" \
              --justification="$ISSUE_LINK" \
              --location=global \
              --project="cell-${TENANT_ID}"
    ```

- Get access with console: [dev](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=cell-c01j2t2v563b55mswz) | [prod](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=cell-c01j2gdw0zfdafxr6)

Admin access provides typical operational readwrite abilities for managing cell infrastructure.

This level of access requires an approver, and typically will also link to an issue detailing why the access is required.
We should prefer making changes through IaC wherever possible.

> [!note]
> This entitlement requires approval from a member of the `gcp-ops-sg@gitlab.com` Google group.
> **Who can approve**: Any SRE or Infrastructure Manager in this group.
> **Next steps**: Please ask a team member to approve your PAM request.

#### [project_breakglass](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/library/terraform/google-privileged-access-manager/-/blob/346edc2e8c2ecee79b8bf06a23819675d4be644d/predefined-entitlements.tf#L55-L110)

- Get access with `gcloud` access:

    ```sh
    # TENANT_ID: Can be found in the "tenant_id" field in the tenant model in `cells/tissue`.
    # example TENANT_ID="c01j2gdw0zfdafxr6"
    gcloud beta pam grants create \
              --entitlement="gldt-breakglass-entitlement-${TENANT_ID}" \
              --requested-duration="1800s" \
              --justification="$ISSUE_LINK" \
              --location=global \
              --project="cell-${TENANT_ID}"
    ```

- Get access with console: [dev](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=cell-c01j2t2v563b55mswz) | [prod](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=cell-c01j2gdw0zfdafxr6)

Breakglass provides the same level of access as the [`project_admin`](#project_admin) entitlement.

This access does not require an approver. The entitlement is intended to be used
during an incident response when there is low team member availability.

We should use `breakglass` as a last resort when we need to make an emergency change to speed up incident response.

#### Amp

- Get access with `gcloud`

    ```sh
    # AMP_PROJECT_ID for dev: `amp-b6f1`
    # AMP_PROJECT_ID for prod: `amp-3c0d`
    gcloud beta pam grants create \
                    --entitlement="gld-readonly-entitlement" \
                    --requested-duration="1800s" \
                    --justification="$ISSUE_LINK" \
                    --location=global \
                    --project="amp-3c0d"
    ```

- Get access with console: [dev](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=amp-b6f1) | [prod](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=amp-3c0d)

The AMP GCP project has the same entitlements as a Cell, meaning [`project_read`](#project_read), [`proejct_admin`](#project_admin), [`project_breakglass`](#project_breakglass)

### Kubernetes Cluster Access

If you would like to connect to the GKE cluster inside the Cell using `kubectl` on your local machine, you can do so by getting the GKE cluster credentials for the Cell.

> [!note]
> This will work only **after** you have completed requesting access through [PAM] and your request has been approved.

```bash
TENANT_ID="<tenant_id>"

gcloud container clusters get-credentials ${TENANT_ID} \
  --region us-east1 \
  --project cell-${TENANT_ID}
```

# Troubleshooting

## Cluster Not Running Warning

If you see a warning that the cluster is not running, when you attempt to get the cluster credentials for a Kubernetes cluster:

```
WARNING: cluster c01j98xncnbxvaqayp is not RUNNING. The kubernetes API may or may not be available.
```

This may indicate the cluster is being upgraded or in maintenance.
Check the cluster status in the GCP/AWS console or try again some time later.

[PAM]: https://cloud.google.com/iam/docs/pam-overview
[cell c01k21yz9qqajjfn6z]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/blob/e8d02618daf54e9dd5576dff7606388396335f80/rings/cellsdev/0/c01k21yz9qqajjfn6z.json#L75
[Amp project]: https://ops.gitlab.net/gitlab-com/gl-infra/gitlab-dedicated/amp
[Identity Center]: https://aws.amazon.com/iam/identity-center/

[^1]: These steps are from the Dedicated [guide](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/runbooks/break-glass.md#gui)
