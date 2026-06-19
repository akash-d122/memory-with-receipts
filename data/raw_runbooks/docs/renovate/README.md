# Renovate at GitLab: Current Implementation Documentation

## Overview

[Renovate](https://github.com/renovatebot/renovate) is a dependency update tool used at GitLab to automate the process of keeping dependencies up-to-date. This document outlines the current implementation, configurations, and workflows of Renovate within the GitLab infrastructure.

## Current Implementation Approaches

GitLab currently uses two different approaches for Renovate:

### 1. Common CI Tasks Approach

**Repository**: [https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks)

**Key Characteristics**:

- Per-project CI job implementation
- Requires CI include and `renovate.json` configuration. This can be generated for you using our [`common-template-copier` template](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/docs/project-templates.md).
- Uses custom container image with specific tooling installed

**Focus Areas**:

- Security and isolation by running one job per project
- Custom tooling baked into the image to generate/update templates and non-standard files

**Documentation**:

- [Main documentation](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/renovate-bot.md)
- [Project setup guide](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/docs/project-setup.md)
- [Configuration file](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/renovate-bot.yml)

### 2. Global Renovate Runner Approach

**Repositories**:

- [https://gitlab.com/gitlab-com/gl-infra/renovate/renovate-ci](https://gitlab.com/gitlab-com/gl-infra/renovate/renovate-ci)
- [https://ops.gitlab.net/gitlab-com/gl-infra/renovate/renovate-ci](https://ops.gitlab.net/gitlab-com/gl-infra/renovate/renovate-ci)

**Key Characteristics**:

- Global CI job with auto-discovery via renovate-runner
- Sets a `managed-by-soos` topic to prevent duplication with the `common-ci-tasks` approach
- Requires `renovate.json` configuration
- Language-specific images based on project code/files

**Focus Areas**:

- Low maintenance and easy onboarding
- Efficiency through running a global CI job that caches dependencies data for all projects
- Uses upstream maintained components

**Documentation**:

- [Main documentation](https://gitlab.com/gitlab-com/gl-infra/renovate/renovate-ci/-/blob/main/README.md?ref_type=heads)

## Future Considerations

We will likely be deprecating the Global Renovate Runner approach, so please set up all new projects using `common-ci-tasks`.

## Adding dependencies

To configure Renovate Bot for a given project, follow the [Automated Project Setup](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/docs/project-setup.md?ref_type=heads#automated-project-setup) documentation in `common-ci-tasks`.

## Related Resources

- [Renovate official documentation](https://docs.renovatebot.com/)
- [GitLab Renovate epic](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/1479)
- [Consolidation issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16148)

## Best Practices

[Renovate best practices](https://gitlab.com/gitlab-com/gl-infra/common-ci-tasks/-/blob/main/renovate-bot.md#best-practices) are documented in the `common-ci-tasks` project.

## Troubleshooting

### Dependency not being picked up

If you configured a dependency and it isn't getting picked up by Renovate
check the output of the latest scheduled pipeline job.

Common CI Tasks:  Scheduled pipeline on the project in question.
Renovate CI:

- Scheduled pipeline for [GitLab.com](https://gitlab.com/gitlab-com/gl-infra/renovate/renovate-ci/-/pipeline_schedules)
- [ops.gitlab.net](https://ops.gitlab.net/gitlab-com/gl-infra/renovate/renovate-ci/-/pipeline_schedules).

If you need further debug data, check the `renovate-log.ndjson` file on the CI
job's artifacts and grep for the project's name.

### Testing out Renovate changes

If you suspect your `renovate.json` may need adjustments, you can try them out
before merging them the following way:

- `npm install -g renovate`
- On a local copy of <https://gitlab.com/gitlab-com/gl-infra/renovate/renovate-ci>,
  execute

```
RENOVATE_PLATFORM=gitlab RENOVATE_TOKEN=<your-gitlab-token> RENOVATE_REPOSITORIES=gitlab-com/gl-infra/<path-to-project> RENOVATE_BASE_BRANCHES=<your-branch> renovate --use-base-branch-config=merge --autodiscover=false --dry-run=full
```
