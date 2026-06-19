## Overview

This runbook is specifically about GitLab Duo Agentic Chat troubleshooting. For regular Duo Chat, please check out the [Duo Chat Runbook](../runway/README.md#how-do-i-rollback) instead.

## Quick Links

Note: these links are mostly for Duo Workflow as a whole, since Agentic Chat uses the Workflow infrastructure.

- [Langsmith traces](https://smith.langchain.com/o/477de7ad-583e-47b6-a1c4-c4a0300e7aca/projects/p/a86cfa18-72b2-4729-844e-94d4ffb7f54a?timeModel=%7B%22duration%22%3A%227d%22%7D&searchModel=%7B%22filter%22%3A%22and%28eq%28is_root%2C+true%29%2C+and%28eq%28metadata_key%2C+%5C%22workflow_type%5C%22%29%2C+eq%28metadata_value%2C+%5C%22chat%5C%22%29%29%29%22%7D)
- [Sentry error tracking](https://new-sentry.gitlab.net/organizations/gitlab/issues/?limit=5&project=36&query=&sort=freq&statsPeriod=14d)
- [Grafana Service Overview](https://dashboards.gitlab.net/d/duo-workflow-svc-main/duo-workflow-svc-overview)
- [Logs for gitlab.com](https://cloudlogging.app.goo.gl/5zAqZnsS2pdrgn4S8)
- [Logs for staging.gitlab.com](https://cloudlogging.app.goo.gl/76p7VVzJr4aLSGua8)

## Before starting the investigation

NOTE: Do **NOT** expose customer's RED data in public issues. Redact them or make a confidential issue if you're unsure.

Before starting the investigation, please collect the following information:

- User name who encountered the bug (e.g. `@johndoe`)
- What happened (e.g. User asked a question in Agentic Duo Chat and the chat did not respond)
- When it happened (e.g. Around 2024/09/16 01:00 UTC)
- GitLab Workflow VS Code extension version (e.g. v.6.26.1)
- How often it happens (e.g. It happens everytime)
- Steps to reproduce (e.g. 1. Ask a question "xxx" 2. Click ...)
- AI Gateway or self-managed AI Gateway (If they use custom models, it's likely latter.)
- A link to a Slack discussion, if any.

## Rollback procedures

If there is an error identified in the Duo Workflow Service, you will have to [rollback the deployment](../runway/README.md#how-do-i-rollback) using Runway. Declare an incident and ask an SRE for help if you do not have the ability to do this.

If there is an error identified in the LSP or VS Code extension, follow these steps to [contact the Editor Extensions team](../editor-extensions/README.md#contacting-the-editor-extensions-team).

## Relevant Slack channel

If you have a problem with Agentic Chat, the best place to ask for help is the `#subteam-duo-chat-workflow-service` Slack channel.
