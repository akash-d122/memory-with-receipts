# Package registry

## Summary

The package registry is used as a private or public registry for a variety of supported package managers.

The following package types are supported:

* [Maven](https://docs.gitlab.com/user/packages/maven_repository/) (Generally available)
* [npm](https://docs.gitlab.com/user/packages/npm_registry/) (Generally available)
* [Nuget](https://docs.gitlab.com/user/packages/nuget_repository/) (Generally available)
* [PyPI](https://docs.gitlab.com/user/packages/pypi_repository/) (Generally available)
* [Terraform](https://docs.gitlab.com/user/packages/terraform_module_registry/) (Generally available)
* [Generic packages](https://docs.gitlab.com/user/packages/generic_packages/) (Generally available)
* [Composer](https://docs.gitlab.com/user/packages/composer_repository/) (Beta)
* [Helm](https://docs.gitlab.com/user/packages/helm_repository/) (Beta)
* [Conan 1](https://docs.gitlab.com/user/packages/conan_1_repository/) (Experiment)
* [Conan 2](https://docs.gitlab.com/user/packages/conan_2_repository/) (Experiment)
* [Debian](https://docs.gitlab.com/user/packages/debian_repository/) (Experiment)
* [Go](https://docs.gitlab.com/user/packages/go_proxy/) (Experiment)
* [Ruby gems](https://docs.gitlab.com/user/packages/rubygems_registry/) (Experiment)

### Runbooks

* [Maven](maven-runbook.md)
* [PyPI runbook](pypi-runbook.md)
* [NPM runbook](npm-runbook.md)
* [Dependency proxy for containers runbook](dependency-proxy-for-containers-runbook.md)
* [NuGet runbook](nuget-runbook.md)
* [Terraform runbook](terraform-module-registry-runbook.md)
* [Generic package runbook](generic-package-runbook.md)

### Dependencies

* [GitLab Rails Console](https://docs.gitlab.com/administration/operations/rails_console/) (authentication, API, GraphQL)
* [PostgreSQL database](https://docs.gitlab.com/omnibus/settings/database/) (package metadata storage)
* [Redis](https://docs.gitlab.com/omnibus/settings/redis/) (session management)
* [Google Cloud](https://docs.gitlab.com/administration/object_storage/#google-cloud-storage-gcs) (object storage)
* [Workhorse](https://docs.gitlab.com/development/workhorse/)
* [Sidekiq](https://docs.gitlab.com/administration/sidekiq/)

## Observability

* [Grafana Dashboard](https://dashboards.gitlab.net/d/stage-groups-package_registry/stage-groups-package-registry)

## Troubleshooting

Historically, package registry issues have been related to code changes or performance issues (for example, HTTP response times or slow database queries).

Below are some steps to diagnose common issues.

### Identify code changes

To check the latest commits from package registry related files, including EE code, run the following command:

`git log -10 --pretty=format:"%h %ad %an: %s" --date=short -- "lib/**/*package*"  "app/graphql/**/*package*" "app/helpers/**/*package*" "app/policies/**/*package*" "app/policies/group_policy.rb" "app/policies/project_policy.rb" "ee/**/*package*"`

### Monitor performance issues

Check the main package registry [Grafana dashboard](https://dashboards.gitlab.net/d/stage-groups-package_registry/stage-groups-package-registry)
for an overview of metrics for each supported package endpoint.

Metrics include:

* API request rates
* API latency
* PostgreSQL latency per query
* Sidekiq completion and error rates

Use Kibana to dig deeper by running queries based on the `correlation_id`.

If there is a Sentry alert, the `correlation_id` can be found under `Tags`.

Alternatively you can identify the `correlation_id` for a request in Kibana using the column `json.correlation_id`.

The `correlation_id` links the request to services involved in processing the request (like GitLab Rails, PostgreSQL, Redis, Workhorse, and Sidekiq).

## Alerts

* [Sentry alerts](https://new-sentry.gitlab.net/organizations/gitlab/alerts/rules/gitlabcom/16/details/)

## References

* [GitLab Package Registry documentation](https://docs.gitlab.com/user/packages/package_registry/)

## Primary Contacts

* **Primary Owner:** Package registry team
* **Slack Channel:** `#g_package-registry` (GitLab internal)
* **Issue Tracker:** [Package registry issues](https://gitlab.com/groups/gitlab-org/-/issues/?sort=due_date_desc&state=opened&label_name%5B%5D=group%3A%3Apackage%20registry&first_page_size=20)
