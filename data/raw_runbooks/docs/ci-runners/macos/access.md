#### How to access macOS hosts and job VMs?

**Table of Contents**

[TOC]

macOS instances are currently hosted in AWS. SRE should have access to the Production environment via Okta.

### Production via Okta

All SRE should have access to the macOS Production environment through Okta:

- Go to Okta.
- Click `AWS Services Org`.
- Under `AWS Account` pick `saas-mac-runners-b6fd8d28`.

Most of the resources exist in the `N. Virginia` (`us-east-1`) region; if you're looking for more info, go to [resources.md](./resources.md) for information about the used resources.

*NOTE*: if you don't see `AWS Services Org`, then open an individual [Access Request](https://gitlab.com/gitlab-com/team-member-epics/access-requests/-/issues), to get access to the AWS account:  `saas-mac-runners-b6fd8d28`. See past [bulk access request](https://gitlab.com/gitlab-com/team-member-epics/access-requests/-/issues/21531).

### SSH Access to macOS Instances

**Important**: The pem files for accessing Mac instances are stored in their associated runner managers.
To SSH into a Mac instance in AWS, you must first SSH into the [associated runner manager in the GCP project](https://console.cloud.google.com/compute/instances?authuser=0&inv=1&invt=AbxZAQ&project=gitlab-ci-155816&pageState=%28%2522instances%2522%3A%28%2522f%2522%3A%2522%25255B%25257B_22k_22_3A_22_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22macos_5C_22_22%25257D%25255D%2522%29%29) `gitlab-ci-155816`, then SSH from the runner manager to the Mac instances.

In order to access a runner manager, a user will need to configure their Yubikey and have a user configuration entered in the [chef repo data bag](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master/data_bags/users). For more information on Yubikey setup, refer to [Yubikey documentation](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/uncategorized/yubikey.md).

1. **SSH into Runner Manager**:

   ```
   ssh userid@runners-manager-saas-macos-large-m2pro-blue-1.c.gitlab-ci-155816.internal
   ```

2. **From Runner Manager to Mac Instance**:

   ```
   sudo ssh -i /etc/gitlab-runner/macos-ssh-key.pem ec2-user@PRIVATE_IP4
   ```

For detailed information on SSH access to job VMs and debugging, refer to [debugging.md](./debugging.md).

### Staging access via gitlabsandbox

If you think you have the appropriate access in the sandbox, you can view the Staging environment following these steps:

- Go to the [sandbox](https://gitlabsandbox.cloud/cloud/accounts/5442c67c-1673-4351-b85d-e366c328bfea)
- Choose `eng-dev-verify-runner`.
- Click `View IAM Credentials`.
- Click the `AWS Console URL`.
- Copy the username and password; beware that sometimes the copy can produce extra spaces before and after the text.
- Login to AWS.
- Click your username in the upper right corner.
- From the dropdown menu, choose `Switch role`.
- Enter Account ID `251165465090` and IAM Role Name `eng_dev_verify_runner`
- Click `Switch Role`

Just like the Production environment, resources are mostly in `N. Virginia` (`us-east-1`) region, for more info go to [resource.md](./resources.md).
