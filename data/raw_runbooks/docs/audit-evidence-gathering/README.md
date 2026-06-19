# Runbook for audit evidence gathering procedures

## Artifacts and collection methods

To best meet our compliance requirements, we need to provide screen captures or console logs of the collection method used to gather data, as well as the resulting artifacts with the data requested by our auditors (access policies, group memberships, user lists, etc.). All commands executed while gathering evidence should be time/date stamped whenever possible, as they can be a part of the validation chain; for example, when we sign the artifacts we collect with GPG, the corresponding validation will indicate _when_ the file(s) were signed, which can be correlated back to the logs/screenshots of the collection method.

### GPG signing

For each of the sources below, we want to ensure that the artifacts provided can be cryptographically verified to be unaltered. To do this, we use the GPG signing key we created on our yubikey per the yubikey setup guide. This is a work in progress, so some sections may not have the gpg steps added, yet.

In general, we will follow the same overall process for any artifact we sign. All commands should be prepended by `date -u;` to provide a datestamp in the

1. Create the artifact(s)
1. Create checksum file
1. GPG sign all files

### Public keys

The GPG signature(s) can be verified using the collector's public key, which is associated with their GitLab profile and is available at <https://gitlab.com/USERNAME.gpg>. To validate the GPG signature on any artifacts provided, the collector's public key will need to be imported into the local keyring on a system with GPG installed.

```bash
# Download and import the engineer's public key(s) from gitlab.com
curl -sL https://gitlab.com/craig.gpg | gpg --import -
```

Once the public key is added to the local key ring, integrity can be verified via

```bash
gpg --verify SIGNATURE_FILE.asc SIGNED_FILE.json
```

Real example:

```bash
craig@fredjones compliance-3173 % date -u; gpg --verify cust-production-e9b9ab_iam-policy.json.asc cust-production-e9b9ab_iam-policy.json
Tue Mar 15 21:51:05 UTC 2022
gpg: Signature made Tue Mar 15 14:50:01 2022 PDT
gpg:                using RSA key 594B7977CD77CAF0D587F2394041289E9DCB07DF
gpg: Good signature from "Craig Barrett <cbarrett@gitlab.com>" [ultimate]
gpg:                 aka "Craig Barrett <craig@gitlab.com>" [ultimate]
craig@fredjones compliance-3173 %
```

### Gathering the list of Chef Admins / users

1. ssh to the chef server (cinc-01-inf-ops.c.gitlab-ops.internal)
2. Chef admins: These are effectively people who have sudo on the chef- server `sudo getent group production`
3. Should you need to get a list of the chef users (people with access to interact with knife)
`for u in $(sudo chef-server-ctl user-list); do sudo chef-server-ctl user-show $u |head -n 2|sed 's/display_name://g' |sed 's/email://g'|paste -sd "," -; done`

4. chef-repo project admins:  `https://ops.gitlab.net/api/v4/projects/139/members/all?sort=access_level_desc&per_page=200` and parse for users who are level 40 or above per <https://docs.gitlab.com/ee/api/members.html>

### Gathering the list of people with production access

clone down [chef repo](https://ops.gitlab.net/gitlab-cookbooks/chef-repo)
Rails console: `ruby bin/prod_access_report.rb -a rails-console`
DB console: `ruby bin/prod_access_report.rb -a db-console`

## GCP project access

### Project IAM policy

In order to represent a complete picture of who has access, we use the `get-ancestors-iam-policy` to also include inherited policies from the parent organization and (sub-)folders.

1. Save the policy json to a file
    `date -u; gcloud projects get-ancestors-iam-policy PROJECT_ID --format=json >PROJECT_ID_iam-policy.json`
1. Checksum the file
    `date -u; sha256sum PROJECT_ID_iam-policy.json >PROJECT_ID_iam-policy.sha256sum
1. GPG sign both
    `date -u; gpg --detach-sign --armor PROJECT_ID_iam-policy.sha256sum`
    `date -u; gpg --detach-sign --armor PROJECT_ID_iam-policy.json`
1. Provide a screenshot or console log of the above commands alongside the resultant files; the timestamps can be correlated with the signature (see validation example below)

#### Validation

To verify the integrity of the files, the checksums validate that the content hasn't changed, and the signatures validate that the files were created/sent by the individual performing the collection steps.

```bash
craig@fredjones compliance-3173 % ls -l
total 32
-rw-r--r-- 1 craig staff 18807 Mar 22 11:46 cust-production-e9b9ab_iam-policy.json
-rw-r--r-- 1 craig staff   833 Mar 22 12:08 cust-production-e9b9ab_iam-policy.json.asc
-rw-r--r-- 1 craig staff   105 Mar 22 12:04 cust-production-e9b9ab_iam-policy.sha256sum
-rw-r--r-- 1 craig staff   833 Mar 22 12:07 cust-production-e9b9ab_iam-policy.sha256sum.asc
craig@fredjones compliance-3173 %

# Validated the content
craig@fredjones compliance-3173 % date -u; sha256sum -c cust-production-e9b9ab_iam-policy.sha256sum
Tue Mar 22 19:26:33 UTC 2022
cust-production-e9b9ab_iam-policy.json: OK
craig@fredjones compliance-3173 %

# Validate the collector's identity
craig@fredjones compliance-3173 % date -u; gpg --verify cust-production-e9b9ab_iam-policy.sha256sum.asc cust-production-e9b9ab_iam-policy.sha256sum

Tue Mar 22 19:26:50 UTC 2022
gpg: Signature made Tue Mar 22 12:07:54 2022 PDT
gpg:                using RSA key 594B7977CD77CAF0D587F2394041289E9DCB07DF
gpg: Good signature from "Craig Barrett <cbarrett@gitlab.com>" [ultimate]
gpg:                 aka "Craig Barrett <craig@gitlab.com>" [ultimate]
craig@fredjones compliance-3173 % date -u; gpg --verify cust-production-e9b9ab_iam-policy.json.asc cust-production-e9b9ab_iam-policy.json

Tue Mar 22 19:27:06 UTC 2022
gpg: Signature made Tue Mar 22 12:08:02 2022 PDT
gpg:                using RSA key 594B7977CD77CAF0D587F2394041289E9DCB07DF
gpg: Good signature from "Craig Barrett <cbarrett@gitlab.com>" [ultimate]
gpg:                 aka "Craig Barrett <craig@gitlab.com>" [ultimate]
craig@fredjones compliance-3173 %
```

### Group memberships

The project IAM policy does not enumerate the group memberships to provide a list of all users with access to the project. For this we follow a similar pattern, but we extract all groups from the policy, and list the members for each.

1. `gcloud beta identity groups memberships list --group-email="gcp-ops-sg@gitlab.com" |grep id|sed 's/id://g'`
2. `gcloud beta identity groups memberships list --group-email="gcp-owners-sg@gitlab.com" |grep id|sed 's/id://g'`

## Production Server list (Server lists for bastions, production servers, database servers)

Clone down [chef repo](https://ops.gitlab.net/gitlab-cookbooks/chef-repo) and:
Find the right roles for the 3 above categories.
Run the commands:

- $ knife search node role:gprd-base-bastion -i
- $ knife search node roles:gprd-base -i
- $ knife search node 'roles:gprd-base-db-postgres OR roles:gprd-base-db-patroni' -i

Updates based on the [definition of production](https://gitlab.com/gitlab-com/gl-security/security-assurance/sec-compliance/compliance/-/blob/master/production_definition.md) for how to list machines (compute) that meet this definition:

GitLab.com:

```shell
gcloud config set project gitlab-ops && gcloud compute instances list
gcloud config set project gitlab-production && gcloud compute instances list
gcloud config set project gemnasium-production && gcloud compute instances list
```

CI:

```shell
gcloud config set project gitlab-ci-155816 && gcloud compute instances list --filter="name~'manager'"
gcloud config set project gitlab-org-ci-0d24e2 && gcloud compute instances list --filter="name~'manager'"
gcloud config set project gitlab-ci-plan-free-7-7fe256 && gcloud compute instances list --filter="name~'manager'"
gcloud config set project gitlab-ci-windows && gcloud compute instances list --filter="name~'manager'"
```

License, Version:

```shell
gcloud config set project gs-production-efd5e8 && gcloud compute instances list # home of version.gitlab.com
gcloud config set project license-prd-bfe85b && gcloud compute instances list   # home of license.gitlab.com
```

dev.gitlab.org and customers.gitlab.com:

- as of 2021-03-18, still in Azure as single VMs, get IP/VM information from the Azure portal
