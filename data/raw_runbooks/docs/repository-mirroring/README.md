<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Repository Mirroring Service

* [Service Overview](https://dashboards.gitlab.net/d/source-code-management-mirrors)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22repository-mirroring%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RepositoryMirroring"

## Logging

* [Mirrors by project in Kibana](https://log.gprd.gitlab.net/app/r/s/E5R17)
* [Mirror errors in Kibana](https://log.gprd.gitlab.net/app/r/s/apZLs)

<!-- END_MARKER -->

## Troubleshooting Pointers

* [Mirror Updates Silently Failing](mirror-updates-silently-failing.md)
* [Pull Mirror Overdue Queue is too Large](../sidekiq/large-pull-mirror-queue.md)
* [Pull Mirroring Timeout with Large LFS Files](pull-mirroring-timeout-with-large-lfs-files.md)
* [Troubleshooting Repository Mirroring](https://docs.gitlab.com/user/project/repository/mirror/troubleshooting/)

<!-- ## Summary -->

<!-- ## Architecture -->

<!-- ## Performance -->

## Scalability

Sidekiq capacity is controlled by the `mirror_max_capacity` application setting. In response to mirroring lag or a need to process more mirroring jobs, this setting can be increased if the application has capacity.

This can be done through the Rails console:

```
ApplicationSetting.update_all(mirror_max_capacity: 2500)
```

Or through the [admin API](https://docs.gitlab.com/api/settings/#list-of-settings-that-can-be-accessed-via-api-calls).

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

[repository_update_mirror sidekiq worker dashboard](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq-worker-detail?var-worker=RepositoryUpdateMirrorWorker)

<!-- ## Links to further Documentation -->

## Playbooks

* [Repository Mirroring Technical Playbook](https://internal.gitlab.com/handbook/engineering/tier2-oncall/playbooks/create/repository-mirroring/)

## Contacting the team

Repository mirroring is owned by Create:Source Code Management.

Requests for help can be submitted using the [source code group template](https://gitlab.com/gitlab-com/request-for-help/-/issues/new?description_template=SupportRequestTemplate-SourceCode).

Urgent, or less formal requests can be made directly on Slack in one of our team channels:

* [#g_create_source_code](https://gitlab.enterprise.slack.com/archives/CK75EF2A2) (general)
* [#g_create_source-code-review-fe](https://gitlab.enterprise.slack.com/archives/CS5NHHBJ7) (frontend)
* [#g_create_source_code_be](https://gitlab.enterprise.slack.com/archives/CNU5W2F5M) (backend)
