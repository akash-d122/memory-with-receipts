# Staging ref

## Logging

* [Stackdriver Logs](https://console.cloud.google.com/logs/query?project=gitlab-staging-ref)

## Troubleshooting Pointers

<!-- END_MARKER -->

## Summary

Staging ref is a deployment of a reference architecture using [GitLab Environment Toolkit](https://gitlab.com/gitlab-org/gitlab-environment-toolkit/-/blob/main/docs/environment_advanced_hybrid.md).

## Architecture

Staging ref has a [hybrid architecture](https://docs.gitlab.com/ee/administration/reference_architectures/10k_users.html#cloud-native-hybrid-reference-architecture-with-helm-charts-alternative). The hybrid architecture consists of webservice and Sidekiq running in a Kubernetes cluster and Gitaly, PostgreSQL, and Redis are run in VMs.

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

For more information see [GET monitoring setup](/get-monitoring-setup.md)

## Links to further Documentation

* [https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref)
* [Staging Ref environment documentation in Handbook](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/environments/staging-ref/)
