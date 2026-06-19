# Wikis

## Contact info

Slack channel: [#g_knowledge](https://gitlab.enterprise.slack.com/archives/C04R571QF5E)

[Handbook](https://handbook.gitlab.com/handbook/product/categories/features/#knowledge)

~"group::knowledge" is responsible for all wiki features except Geo integration (`feature_category: wiki`).

## Services used

[Web](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/web) and [API](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/api) for serving Rails and API requests
[Redis](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/redis) for caching
[Sidekiq](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/sidekiq) for asynchronous jobs
PostgreSQL for wiki page metadata and wiki page comments
[Gitaly](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/gitaly) for getting data from wiki git repositories

## Logging

### Kibana

- [Wiki failed requests breakdown by error message (last 7 days)](https://log.gprd.gitlab.net/app/lens#/edit/9197327b-e6ef-411a-9511-7515c6320740?_g=(filters:!(),refreshInterval:(pause:!t,value:60000),time:(from:now-7d,to:now)))

These logs show all failed Rails requests and jobs. They can be filtered by:

- Specific action/endpoint by `json.meta.caller_id`
- Specific job class by `json.class`
- By correlation ID by `json.correlation_id`

### Sentry

- [Wiki errors in Sentry](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=is%3Aunresolved+feature_category%3Awiki&referrer=issue-list&statsPeriod=7d)

### Grafana

- [Knowledge stage error budget details](https://dashboards.gitlab.net/d/stage-groups-detail-knowledge)
- [web: Project-level Wiki](https://dashboards.gitlab.net/d/web-rails-controller/web3a-rails-controller?var-controller=Projects::WikisController)
- [web: Group-level Wiki](https://dashboards.gitlab.net/d/web-rails-controller/web3a-rails-controller?var-controller=Groups::WikisController)
- [api: Project-level Wiki](https://dashboards.gitlab.net/d/api-rails-controller/api3a-rails-controller?var-action=GET%20%2Fapi%2Fprojects%2F:id%2Fwikis&var-action=GET%20%2Fapi%2Fprojects%2F:id%2Fwikis%2F:slug&var-action=PUT%20%2Fapi%2Fprojects%2F:id%2Fwikis%2F:slug&var-action=POST%20%2Fapi%2Fprojects%2F:id%2Fwikis&var-action=POST%20%2Fapi%2Fprojects%2F:id%2Fwikis%2Fattachments&var-action=DELETE%20%2Fapi%2Fprojects%2F:id%2Fwikis%2F:slug&var-action=%2Fapi%2Fprojects%2F:id%2Fwiki)
- [api: Group-level Wiki](https://dashboards.gitlab.net/d/api-rails-controller/api3a-rails-controller?var-action=GET%20%2Fapi%2Fgroups%2F:id%2Fwikis&var-action=GET%20%2Fapi%2Fgroups%2F:id%2Fwikis%2F:slug&var-action=PUT%20%2Fapi%2Fgroups%2F:id%2Fwikis%2F:slug&var-action=POST%20%2Fapi%2Fgroups%2F:id%2Fwikis%2Fattachments&var-action=%2Fapi%2Fgroups%2F:id%2Fwiki)
- [sidekiq: Wikis::GitGarbageCollectWorker](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq3a-worker-detail?var-worker=Wikis::GitGarbageCollectWorker)
- [sidekiq: GroupWikis::GitGarbageCollectWorker](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq3a-worker-detail?var-worker=GroupWikis::GitGarbageCollectWorker)

## Troubleshooting

- [Diagnosis with Kibana](../onboarding/kibana-diagnosis.md)

### "This page could not be displayed because it timed out. You can view the source or clone the repository."

Currently, wiki repositories don't have a manual way to run a repository housekeeping service, housekeeping is only performed after a set amount of commits or git pushes to the repository.

In the case the repo gets slow enough that pages time out, housekeeping has to be done manually by cloning the repository and force pushing the repo.

### "remote: A repository for this group wiki does not exist yet."

If accessing a group wiki repository through Git shortly after the group's creation, the repository might not have been initialized yet. Wait 1 minute or create a page through the web UI.
