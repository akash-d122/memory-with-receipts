# Metrics Catalog

The Metrics-Catalog is a declarative approach to monitoring GitLab using Service-Level Monitoring.

At present, the documentation on the Metrics-Catalog requires some work, but there are several conference talks on the approach we use:

* <https://www.youtube.com/watch?v=CbX1nZL7biQ>
* <https://www.youtube.com/watch?v=6sfr2IGJQXk>
* <https://www.youtube.com/watch?v=YHV0qkKBz7o>
* <https://vimeo.com/341141334>
* <https://www.youtube.com/watch?v=2zL9DymXi1E>
* <https://www.youtube.com/watch?v=swnj6KTRg08>

## Source Locations

The metrics-catalog source can be found in the following locations in this project:

1. [`metrics-catalog`](../../metrics-catalog/) - the GitLab.com Metrics-Catalog.
1. [`reference-architectures/get-hybrid`](../../reference-architectures/get-hybrid/) - A [Reference Architecture](https://docs.gitlab.com/ee/administration/reference_architectures/) Metrics-Catalog for a [GitLab Environment Toolkit](https://gitlab.com/gitlab-org/gitlab-environment-toolkit) Hybrid (VM+Kubernetes) GitLab deployment
1. [`libsonnet`](../../libsonnet/) - common source-code, written in [Jsonnet](https://jsonnet.org), for generating the configuration.
