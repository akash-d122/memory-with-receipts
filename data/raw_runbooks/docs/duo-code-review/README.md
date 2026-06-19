# Duo Code Review Runbook

## Overview

This page explains how to investigate Duo Code Review issues on production.

## Dashboard

- [Kibana based dashboard](https://log.gprd.gitlab.net/app/dashboards#/view/f959393c-82c1-4b69-a4d3-2446aab9476c?_g=(refreshInterval:(pause:!t,value:60000),time:(from:now-7d,to:now)))
- [Error budget dashboard](https://dashboards.gitlab.net/d/stage-groups-detail-code_creation/c704560?orgId=1&from=now-28d%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main)
- [Duo Code Review Chat Worker](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq3a-worker-detail?orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=MergeRequests::DuoCodeReviewChatWorker)
- [Tableau (Unit Primitives)](https://10az.online.tableau.com/#/site/gitlab/views/AIGatewayReporting/Overview?:iid=1) - filter with `review_merge_request`
- Alerts - implementation tracked in [follow up issue](https://gitlab.com/gitlab-org/gitlab/-/issues/570459)

## Summary

Duo Code Review is an AI-powered feature that provides automated code review capabilities for merge requests. It helps ensure consistent code review standards and provides intelligent feedback on code changes using LLMs.

It can be [enabled by default](https://docs.gitlab.com/user/project/merge_requests/duo_in_merge_requests/#automatic-reviews-from-gitlab-duo-for-a-project) so that `GitLabDuo` automatically reviews merge requests, or it can be added manually as a reviewer for on-demand reviews when needed.

**Key Features:**

- Automatic reviews of merge requests by @GitLabDuo
- Interactive code review discussions
- Custom review instructions per project
- Integration with GitLab's merge request workflow

## Architecture

Duo Code Review follows a similar architecture to other GitLab Duo features:

1. **Frontend:** Vue.js components in merge request interface
1. **Backend:** Rails GraphQL API and services
1. **AI Gateway:** Processes prompts and communicates with LLMs
1. **LLM Integration:** Claude/other models for code analysis and review response

For a high-level diagram of the basic internal flow in Rails, refer to [this diagram](https://gitlab.com/gitlab-com/create-stage/code-review-be/-/wikis/Duo-Code-Review#basic-internal-flow)

## Prerequisites & Access Control

**Licensing Requirements:**

- Tier: Premium, Ultimate
- Add-on: GitLab Duo Enterprise

**Permissions:**

- Maintainer role required to enable automatic reviews
- Developer role required to interact with @GitLabDuo in merge requests

## Troubleshooting

### Common Issues

| Problem                                                               | Solution                                                                                                                                                                                                                                                                              |
|-----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `@GitLabDuo` not reviewing MR | Ensure MR is not in the draft state |
| `@GitLabDuo` not appearing in the reviewers tab | Check licensing and permissions |
| Custom instructions not working | Verify `.gitlab/duo/mr-review-instructions.yaml` [format](https://docs.gitlab.com/user/project/merge_requests/duo_in_merge_requests/#customize-instructions-for-gitlab-duo-code-review) |
| Reviews taking too long | Check AI Gateway connectivity as well as LLMs' status |
| Duo Code Review not available on self-managed | Verify the GitLab instance is running minimum version `17.10` or higher and check if the @GitLabDuo user exists on the instance |

## Monitoring & Observability

### Logs to Monitor

- `llm.log` - AI request debugging
- `sidekiq_json.log` - Background job processing
- `graphql_json.log` - GraphQL API requests

## Production Considerations

### Performance

- Reviews are processed asynchronously via Sidekiq
- Large merge requests may take longer to review

## Feature Flags

Current feature flags:

- `cascading_auto_duo_code_review_settings` - Group/application level settings (Beta)

## Support & Escalation

**Before escalating**

NOTE: Do **NOT** expose customer's RED data in public issues. Redact them or make a confidential issue if you're unsure.

Before starting the investigation and escalating, please collect the following information:

- User name who encountered the bug (e.g. `@janedoe`)
- Type of instance the user is on (e.g. SaaS, self-managed)
- What happened (e.g. User requested for a review from `@GitLabDuo` and saw an error code `A3010`)
- When it happened (e.g. Around 2025/09/07 01:00 UTC)
- Where it happened (e.g. MR discussion, review panel)
- How often the issue occurs (e.g. It happens everytime)
- Steps to reproduce (e.g. 1. Ask a follow question to review "xxx" 2. Click ...)
- A link to a Slack discussion, if any.

and create an issue in the [GitLab Issue tracker](https://gitlab.com/gitlab-org/gitlab/-/issues) and ping `@gitlab-org/code-creation/engineers`

### Internal Support

- **Primary Team:** [Code Creation](https://handbook.gitlab.com/handbook/engineering/ai/code-creation/)
- **Slack Channel:** #g_code_creation
- **On-call:** Follow standard GitLab on-call procedures

## User Support

- [Documentation](https://docs.gitlab.com/user/project/merge_requests/duo_in_merge_requests/)
- Feature feedback: [Issue 517386](https://gitlab.com/gitlab-org/gitlab/-/issues/517386)
