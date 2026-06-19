# Deploy docker-machine

We have our fork of `docker-machine` available at
<http://gitlab.com/gitlab-org/ci-cd/docker-machine> which we use for
GitLab.com Linux shared runners. A list of releases can be found in
<https://gitlab.com/gitlab-org/ci-cd/docker-machine/-/releases>.

Deploying a new version of `docker-machine` requires **no** downtime,
and only requires a chef role change.

## Rollout

To deploy a new version of `docker-machine` open a [Criticality 3 Change Management issue](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/#criticality-3),
which should specify the rollout strategy below.

### Prerequisites

1. [ ] Determine which version to deploy by looking at <https://gitlab.com/gitlab-org/ci-cd/docker-machine/-/releases>.
1. [ ] Determine the checksum for `docker-machine-Linux-x86_64` binary by
download the `release.sha256` from the [index page of the
release](https://gitlab-docker-machine-downloads.s3.amazonaws.com/v0.16.2-gitlab.9/index.html).

### Update `prmX`

1. [ ] Create a merge request to add `override_attributes` inside of
[`roles/gitlab-runner-prm.json`](https://ops.gitlab.net/gitlab-cookbooks/chef-repo/-/blob/master/roles/gitlab-runner-prm.json)
to specify a different version of `docker-machine`.

    <details>
    <summary> roles/gitlab-runner-prm.json </summary>

    ```json
    "override_attributes": {
      "cookbook-gitlab-runner": {
        "docker-machine": {
          "version": "0.16.2-gitlab.9",
          "source": "https://gitlab-docker-machine-downloads.s3.amazonaws.com/v0.16.2-gitlab.9/docker-machine-Linux-x86_64",
          "checksum": "75522b4a816c81b130e7fb6f07121c1d5ea4165c4df5fbf05663eac88b797f02"
        }
      }
    },
    ```

    </details>
1. [ ] Merge the merge request.
1. [ ] Run the `apply_to_prod` job on the merge commit.
1. [ ] Run `chef-client` on the nodes: `knife ssh -C2 -afqdn 'roles:gitlab-runner-prm' -- 'sudo -i chef-client'`.
1. [ ] Monitor the following:
    1. [`runner_system_failure` metrics](https://dashboards.gitlab.net/d/000000159/ci?viewPanel=82&orgId=1&var-shard=All&var-runner_type=All&var-runner_managers=All&var-gitlab_env=gprd&var-gl_monitor_fqdn=All&var-has_minutes=yes&var-runner_job_failure_reason=runner_system_failure&var-jobs_running_for_project=0&var-runner_request_endpoint_status=All)
    1. [ci-runner apdex](https://dashboards.gitlab.net/d/ci-runners-main/ci-runners-overview?viewPanel=79474957&orgId=1&var-PROMETHEUS_DS=Global&var-environment=gprd&var-stage=main&var-sigma=2)

### Update rest of the runner fleet

1. Create a merge request
    1. [ ] Remove the
    `override_attributes.cookbook-gitlab-runner.docker-machine` from
    `roles/gitlab-runner-prm.json` that was added previous steps.
    1. [ ] Update `default_attributes.cookbook-gitlab-runner.docker-machine`
    inside of
    [`roles/gitlab-runner-base.json`](https://ops.gitlab.net/gitlab-cookbooks/chef-repo/-/blob/master/roles/gitlab-runner-base.json)
    to the version that you want to update the rest of the runner fleet.

        <details>
        <summary> roles/gitlab-runner-base.json </summary>

        ```json
        "default_attributes": {
          ...
          "cookbook-gitlab-runner": {
            "docker-machine": {
              "version": "0.16.2-gitlab.9",
              "source": "https://gitlab-docker-machine-downloads.s3.amazonaws.com/v0.16.2-gitlab.9/docker-machine-Linux-x86_64",
              "checksum": "75522b4a816c81b130e7fb6f07121c1d5ea4165c4df5fbf05663eac88b797f02"
            },
            ...
          }
        },
        ```

        </details>
    1. [ ] Update `default_attributes.cookbook-gitlab-runner.docker-machine`
    inside of
    [`roles/org-ci-base-runner.json`](https://ops.gitlab.net/gitlab-cookbooks/chef-repo/-/blob/master/roles/org-ci-base-runner.json)
    to the version that you want to update the rest of the runner fleet.

        <details>
        <summary> roles/org-ci-base-runner.json </summary>

        ```json
        "default_attributes": {
          ...
          "cookbook-gitlab-runner": {
            "docker-machine": {
              "version": "0.16.2-gitlab.9",
              "source": "https://gitlab-docker-machine-downloads.s3.amazonaws.com/v0.16.2-gitlab.9/docker-machine-Linux-x86_64",
              "checksum": "75522b4a816c81b130e7fb6f07121c1d5ea4165c4df5fbf05663eac88b797f02"
            },
            ...
          }
        },
        ```

        </details>
1. [ ] Merge the merge request.
1. [ ] Run the `apply_to_prod` job on the merge commit.
1. [ ] Run `chef-client` on all the nodes: `knife ssh -C2 -afqdn 'roles:gitlab-runner-base OR roles:org-ci-base-runner' -- 'sudo -i chef-client'`.
1. Monitor the following:
    1. [`runner_system_failure` metrics](https://dashboards.gitlab.net/d/000000159/ci?viewPanel=82&orgId=1&var-shard=All&var-runner_type=All&var-runner_managers=All&var-gitlab_env=gprd&var-gl_monitor_fqdn=All&var-has_minutes=yes&var-runner_job_failure_reason=runner_system_failure&var-jobs_running_for_project=0&var-runner_request_endpoint_status=All)
    1. [ci-runner apdex](https://dashboards.gitlab.net/d/ci-runners-main/ci-runners-overview?viewPanel=79474957&orgId=1&var-PROMETHEUS_DS=Global&var-environment=gprd&var-stage=main&var-sigma=2)
