# ChefClientErrorCritical

## Overview

A significant number (10% or more) of Chef nodes are failing to complete chef-client converges in an environment (most likely GPRD).

This can be caused by a recent change to Chef cookbooks, roles, or environments. It can also be caused by third party dependencies, such as apt, not responding, or other services being unreachable. Sometimes it can be caused by cookbook bugs that don't accomodate for all edge cases, etc.

This is not a publically facing problem for GitLab.com users, but it can block deploys and prevent required changes to our Chef instructure.

When paged with this alert, investigate logs and look for chef-client errors. If it's not clear what is wrong, compare the errors to recent changes in cookbooks and the chef-repo project to try and identify the culprit.

## Services

- [config management Service Overview](./README.md)
- Owner: [Runway](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/team/foundations/)

## Metrics

This alert is based off this expression: `avg(chef_client_error{env="gprd"}) * 100 > 10` and its definition can be found in the [Mimir Alert Definition]. This is not an auto-generated alert definition.

`chef_client_error` is a metric scraped from the node exporter on VMs and represents the last result of a chef-cient run as 0 for a success and 1 as a failure.

This alert only notifies if more than 10% of the chef-client runs for the past hour have failed in a single environment. Chef-client does occasioncally fail to run for various reasons. Once the number of failures climbs to 10% or more of the Chef VMs in an environment, the EoC is notified since this could break deploys or needed configuration changes to mitigate incidents, etc.

Normally, this value is less than 10 and ideally is close to 0 with only occasional spikes to 1.

## Alert Behavior

If the cause of chef-client failures is going to take a long time to remedy, a silence may be appropriate. Be aware that silencing this could blind the EoC to another Chef converging problem while silenced.

This should be a rare alert, but it has happened four times in the past ninety days.

[Kibana Trends for ChefClientErrorCritical](https://nonprod-log.gitlab.net/app/r/s/FaUtr)

## Severities

It's likely this is a Severity 3 or lower incident. The inability to converge chef-clients should only affect internal supporters of GitLab.com and their tooling. It should be labeled as `backstage` most likely.

During times of many incidents occuring at the same time, this could be a higher severity if it is blocking our ability to solve other incidents.

## Verification

- [Link to PromQL](https://dashboards.gitlab.net/goto/8Ps-KlySg?orgId=1)
- [Link to GPRD chef-client converge errors](https://log.gprd.gitlab.net/app/r/s/Py7dw)

## Recent changes

- [Recent Chef Related Change Requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=change%3A%3Acomplete&label_name%5B%5D=Service%3A%3AChef&first_page_size=20)
- [Recent Chef Repo Merged MRs](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests?scope=all&state=merged)
- [Recent Chef Cookbook Merged MRs](https://gitlab.com/groups/gitlab-cookbooks/-/merge_requests?scope=all&state=merged)

If you do find an MR that appears strongly correlated and related to the incident in progress, reverting the version change in the [Chef-Repo Project](https://gitlab.com/gitlab-com/gl-infra/chef-repo) should be the quickest and cleanest way to roll back the changes. This would work well for cookbook version increases as well as role changes.

## Troubleshooting

1. Consider breaking down the [chef-client failures by fleet type](https://dashboards.gitlab.net/goto/hDdRA9sSg?orgId=1).
1. Look for errors in the logs for chef-client.
1. Review recent changes to chef-repo.

## Possible Resolutions

- [2024-05-21: Chef failures due to broken upstream apt repo](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18045)
- [2023-05-08: Chef client failures in multiple environments](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/13136)

## Dependencies

Chef cookbooks often rely on third party cookbooks, apt repositories, and the Chef server.

## Escalation

Chef is a shared service and cookbook and chef-repo changes can be made by a large number of individuals. If the problem is isolated to a single fleet, consider escelating to the team that manages that fleet or service to get more help on recent changes, etc.

The [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N) Slack channel might be a good first place to ask for help.

## Definitions

- [Mimir Alert Definition]

When considering modifying this alert, consider that chef-client failures may happen due to outside dependencies, so errors will happen. They key is to prevent blockages for config management work and deploys.

- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/fleet-management/config_management/alerts/ChefClientErrorCritical.md?ref_type=heads)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md?ref_type=heads)

## Related Links

- [Related alerts](./)
- [Chef Troubleshooting](../chef-troubleshooting.md)

[Mimir Alert Definition]: https://gitlab.com/gitlab-com/runbooks/-/blob/f1b8f547a836192fa6a834dd93dea7f84e88a089/mimir-rules/gitlab-gprd/chefs.yml#L17-32
