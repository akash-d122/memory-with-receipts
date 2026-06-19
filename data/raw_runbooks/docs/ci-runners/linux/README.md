# Linux CI/CD Runners fleet configuration management

All of the Linux CI Runners fleet is currently managed through our main
[`chef-repo`](https://ops.gitlab.net/gitlab-cookbooks/chef-repo/).
All nodes are managed by a set of structured roles.

In the context of configuration management we distinguish three topics that are intersecting and need to be understood
before starting the work on any changes:

1. `graceful shutdown` - which is the procedure that allows Runner to be terminated in a way that all users jobs are
   properly finished and not interrupted in the middle.

    As this strictly projects on how our users perceives GitLab.com's Shared Runners stability **it's important to
    understand why graceful shutdown is needed, how to handle it and in which cases it's a hard requirement**.

    To read more about the graceful shutdown procedure please check [graceful-shutdown.md](graceful-shutdown.md).

1. `deployments` - which means an upgrade or downgrade of the GitLab Runner version. **Deployment always needs to be
   done with the usage of the graceful shutdown procedure!**

    To read more about the deployments management please check [deployment.md](deployment.md).

1. `configuration change` - which means any other changes in the Runner Managers configuration. Depending on the type
   of the change it may or may not require the usage of graceful shutdown procedure.

    To read more about the configuration changes management please check [configuration.md](configuration.md).

## Chef roles structure

To find out what `srm`, `gsrm`, `gdsrm` and `prm` means please check the [description](../README.md#runner-descriptions).

The roles are designed with the concept that most configuration is specified in the roles
higher in the structure. More detailed roles overwrite or add only necessary information. As can be seen
on the diagram bellow, most of the runner roles are based at the `gitlab-runner-base` role.

The only exception are GDSRM runners which are rooted in `org-ci-base` role
**and [are managed by terraform](https://ops.gitlab.net/gitlab-com/gitlab-com-infrastructure/-/tree/master/environments/org-ci)**.
Role names follow the SRM/GSRM/GDSRM/PRM naming convention of the runner managers itself.

All runner manager nodes are also added to dedicated chef environments: `ci-prd`, `ci-stg` and `org-ci`.

### Roles dependency

```mermaid
graph LR
    classDef default fill:#e0e0e0,stroke:#000
    r::base(gitlab-runner-base)
    r::base::gce(gitlab-runner-base-gce)
    r::org-ci-base(org-ci-base)
    r::org-ci-base-runner(org-ci-base-runner)

    r::gsrm(gitlab-runner-gsrm)
    r::gsrm-gce(gitlab-runner-gsrm-gce)
    r::gsrm-gce-us-east1-c(gitlab-runner-gsrm-gce-us-east1-c)
    r::gsrm3(gitlab-runner-gsrm3)
    r::gsrm5(gitlab-runner-gsrm5)
    r::gsrm-gce-us-east1-d(gitlab-runner-gsrm-gce-us-east1-d)
    r::gsrm4(gitlab-runner-gsrm4)
    r::gsrm6(gitlab-runner-gsrm6)

    r::prm(gitlab-runner-prm)
    r::prm-gce(gitlab-runner-prm-gce)
    r::prm-gce-us-east1-c(gitlab-runner-prm-gce-us-east1-c)
    r::prm3(gitlab-runner-prm3)
    r::prm-gce-us-east1-d(gitlab-runner-prm-gce-us-east1-d)
    r::prm4(gitlab-runner-prm4)

    r::srm(gitlab-runner-srm)
    r::srm-gce(gitlab-runner-srm-gce)
    r::srm-gce-us-east1-c(gitlab-runner-srm-gce-us-east1-c)
    r::srm3(gitlab-runner-srm3)
    r::srm5(gitlab-runner-srm5)
    r::srm-gce-us-east1-d(gitlab-runner-srm-gce-us-east1-d)
    r::srm4(gitlab-runner-srm4)
    r::srm6(gitlab-runner-srm6)
    r::srm7(gitlab-runner-srm7)

    r::stg-srm(gitlab-runner-stg-srm)
    r::stg-srm-gce(gitlab-runner-stg-srm-gce)
    r::stg-srm-gce-us-east1-c(gitlab-runner-stg-srm-gce-us-east1-c)
    r::stg-srm-gce-us-east1-d(gitlab-runner-stg-srm-gce-us-east1-d)

    r::gdsrm-us-east1-c(org-ci-base-runner-us-east1-c)
    r::gdsrm-us-east1-b(org-ci-base-runner-us-east1-b)
    r::gdsrm-us-east1-d(org-ci-base-runner-us-east1-d)

    n::gsrm3[gitlab-shared-runners-manager-3.gitlab.com]
    n::gsrm4[gitlab-shared-runners-manager-4.gitlab.com]
    n::gsrm5[gitlab-shared-runners-manager-5.gitlab.com]
    n::gsrm6[gitlab-shared-runners-manager-6.gitlab.com]

    n::prm3[private-runners-manager-3.gitlab.com]
    n::prm4[private-runners-manager-4.gitlab.com]

    n::srm3[shared-runners-manager-3.gitlab.com]
    n::srm4[shared-runners-manager-4.gitlab.com]
    n::srm5[shared-runners-manager-5.gitlab.com]
    n::srm6[shared-runners-manager-6.gitlab.com]
    n::srm7[shared-runners-manager-7.gitlab.com]

    n::srm3::stg[shared-runners-manager-3.staging.gitlab.com]
    n::srm4::stg[shared-runners-manager-4.staging.gitlab.com]

    n::gdsrm1[gitlab-docker-shared-runners-manager-01]
    n::gdsrm2[gitlab-docker-shared-runners-manager-02]
    n::gdsrm3[gitlab-docker-shared-runners-manager-03]
    n::gdsrm4[gitlab-docker-shared-runners-manager-04]

    e::ci::stg[ci-stg environment]
    e::ci::prd[ci-prd environment]
    e::org::ci[org-ci environment]

    r::base --> r::gsrm
    r::gsrm --> r::gsrm-gce
    r::base::gce --> r::gsrm-gce
    r::gsrm-gce --> r::gsrm-gce-us-east1-c
    r::gsrm-gce-us-east1-c --> r::gsrm4
    r::gsrm4 ==> n::gsrm4
    r::gsrm-gce-us-east1-c --> r::gsrm6
    r::gsrm6 ==> n::gsrm6
    r::gsrm-gce --> r::gsrm-gce-us-east1-d
    r::gsrm-gce-us-east1-d --> r::gsrm3
    r::gsrm3 ==> n::gsrm3
    r::gsrm-gce-us-east1-d --> r::gsrm5
    r::gsrm5 ==> n::gsrm5

    r::base --> r::prm
    r::prm --> r::prm-gce
    r::base::gce --> r::prm-gce
    r::prm-gce --> r::prm-gce-us-east1-c
    r::prm-gce-us-east1-c --> r::prm4
    r::prm4 ==> n::prm4
    r::prm-gce --> r::prm-gce-us-east1-d
    r::prm-gce-us-east1-d --> r::prm3
    r::prm3 ==> n::prm3

    r::base --> r::srm
    r::srm --> r::srm-gce
    r::base::gce --> r::srm-gce
    r::srm-gce --> r::srm-gce-us-east1-c
    r::srm-gce-us-east1-c --> r::srm4
    r::srm4 ==> n::srm4
    r::srm-gce-us-east1-c --> r::srm6
    r::srm6 ==> n::srm6
    r::srm-gce-us-east1-c --> r::srm7
    r::srm7 ==> n::srm7
    r::srm-gce --> r::srm-gce-us-east1-d
    r::srm-gce-us-east1-d --> r::srm3
    r::srm3 ==> n::srm3
    r::srm-gce-us-east1-d --> r::srm5
    r::srm5 ==> n::srm5

    r::srm --> r::stg-srm
    r::srm-gce --> r::stg-srm-gce
    r::stg-srm --> r::stg-srm-gce
    r::srm-gce-us-east1-c --> r::stg-srm-gce-us-east1-c
    r::stg-srm-gce --> r::stg-srm-gce-us-east1-c
    r::stg-srm-gce-us-east1-c ==> n::srm4::stg
    r::srm-gce-us-east1-d --> r::stg-srm-gce-us-east1-d
    r::stg-srm-gce --> r::stg-srm-gce-us-east1-d
    r::stg-srm-gce-us-east1-d ==> n::srm3::stg

    r::org-ci-base --> r::org-ci-base-runner
    r::org-ci-base-runner --> r::gdsrm-us-east1-c
    r::gdsrm-us-east1-c ==> n::gdsrm1
    r::gdsrm-us-east1-c ==> n::gdsrm4
    r::org-ci-base-runner --> r::gdsrm-us-east1-d
    r::gdsrm-us-east1-d ==> n::gdsrm2
    r::org-ci-base-runner --> r::gdsrm-us-east1-b
    r::gdsrm-us-east1-b ==> n::gdsrm3

    n::gdsrm1 --- e::org::ci
    n::gdsrm2 --- e::org::ci
    n::gdsrm3 --- e::org::ci
    n::gdsrm4 --- e::org::ci

    n::gsrm3 --- e::ci::prd
    n::gsrm4 --- e::ci::prd
    n::gsrm5 --- e::ci::prd
    n::gsrm6 --- e::ci::prd

    n::prm3 --- e::ci::prd
    n::prm4 --- e::ci::prd

    n::srm3 --- e::ci::prd
    n::srm4 --- e::ci::prd
    n::srm5 --- e::ci::prd
    n::srm6 --- e::ci::prd
    n::srm7 --- e::ci::prd

    n::srm3::stg --- e::ci::stg
    n::srm4::stg --- e::ci::stg
```

## Specific cookbooks

Most of the configuration is handled by two Chef cookbooks specific for GitLab Runner:

- [`cookbook-gitlab-runner`](https://gitlab.com/gitlab-cookbooks/cookbook-gitlab-runner) - this one handles most of the
  GitLab Runner configuration. It was intended to be enough generic that other people will be able to use it in their
  chef configuration to manage GitLab Runner.

    Allows to define GitLab Runner version, GitLab Runner configuration, Docker Machine version and installation source.

- [`cookbook-wrapper-gitlab-runner`](https://gitlab.com/gitlab-cookbooks/cookbook-wrapper-gitlab-runner/) - it's
  a wrapper made around the first one. Contains some stuff specific for GitLab.com infrastructure configuration, like
  support for our chef vault, specific administration management script, Runner's systemd configuration adjustment etc.

## Architecture

Linux CI Runners Architecture can be found in [architecture.md](./architecture.md)

## Administrator prerequisites

To manage CI Runners fleet configuration you need to:

- have write access to <https://ops.gitlab.net/gitlab-cookbooks/chef-repo>,
- have write access to <https://ops.gitlab.net/gitlab-com/gitlab-com-infrastructure> (`gdsrmX` managers are managed by terraform)
- have write access to `chef.gitlab.com`,
- have configured `knife` environment,
- have admin access to nodes (sudo access).
- have bastion for `org-ci` runners set up:

    <details>
    <summary> Inside of your `~/.ssh/config`</summary>

    ```ini
    # gitlab-org-ci boxes
    Host *.gitlab-org-ci-0d24e2.internal
    ProxyJump     lb-bastion.org-ci.gitlab.com
    ```

    </details>
