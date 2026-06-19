# Access Management for Vault

## Onboarding a team into Vault

Access to Vault is managed through [Okta](https://gitlab.okta.com), with Okta groups being given access to sets of readonly and read/write secret paths.

> [!note]
> For ease of access auditing and administration, access can not given on a per user basis, only per group.

To obtain access to Vault for your team:

1. Check if an Okta group already exists for your team, ask a member of the CorpSec team if you aren't sure. You can also ask directly in the Access Request below;
2. Open an [Okta Change Request](https://gitlab.com/gitlab-com/gl-security/corp/issue-tracker/-/issues/new?description_template=okta_app_change) with the following:

    * if you don't have Okta group yet, ask for a new Okta group to be created and list the team members to be added to it
      * Group Naming Format: `team-eng-{team-name}`
    * ask for your Okta group to be added to the Vault Production app (`hcp-vault-production`) in Okta **with the groups claim filter enabled**;
    * have the Business Owner of Hashicorp Vault approve the change request.

3. Add your Okta group to the [Vault configuration in the `config-mgmt` project](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/) (ask a member of the Infrastructure team for help if you don't have access to this project or aren't familiar with Terraform):

   * Add your team to the user groups in [`groups.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/vault-production/groups.tf):

     ```terraform
     locals {
       groups = {
         ...
         your_group = [
           "<your Okta group name>",
         ]
       }

       vault_user_groups = setunion(
         ...
         local.groups.your_group,
       )
     }
     ```

   * Define which secret path(s) your team needs access to in [`secret_policies.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/vault-production/secrets_policies.tf), for example:

     ```terraform
     locals {
       ci_secrets_policies = {
         "gitlab-com/gitlab-com/your/project" = {
           admin = {
             groups = local.groups.your_group
           }
         }

         "ops-gitlab-net/gitlab-com/some/other/project" = {
           read = {
             groups = local.groups.your_group
           }
         }
       }
     }
     ```

   * Commit, submit a merge request, get it approved and merged by a member of the [Infrastructure team](https://gitlab.slack.com/archives/CB3LSMEJV).

4. You should now have access to Vault, you can check by trying to login [here](https://vault.gitlab.net/ui/vault/auth?with=oidc%2F) (leave the `Role` field empty).

If you have any issues or special requirements, feel free to reach out to the [Runway team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/team/runway/) to discuss it.
