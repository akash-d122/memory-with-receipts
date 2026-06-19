# Teleport

[Teleport](https://goteleport.com/docs/) is an *Access Management Platform*. It
provides secure, fully auditable access to production hosts, datastores,
kubernetes clusters and other infrastructure. Teleport provides fine-grained
role-based access controls, just-in-time access requests, and authentication via
Okta rather than SSH keys.

<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Teleport Access Platform Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22teleport%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::TeleportCore"


<!-- END_MARKER -->

## Guides

### User Guides

* [Getting Access to Teleport](./getting_access.md)
* [Accessing the Rails Console](./Connect_to_Rails_Console_via_Teleport.md)
* [Accessing a Database](./Connect_to_Database_Console_via_Teleport.md)
* [SSH Access to a Host](./ssh_access.md)
* [Teleport Approval Workflow](./teleport_approval_workflow.md)

### Operations

* [Teleport Administration](./teleport_admin.md)
* [Teleport Disaster Recovery](./teleport_disaster_recovery.md)

## Support

If you have any issues using Teleport, or the approval process,
please ask the Infrastructure Security team in the [#security_help](https://gitlab.enterprise.slack.com/archives/C094L6F5D2A) Slack channel.

If you encounter a bug or problem with Teleport, please [open an issue](https://gitlab.com/gitlab-com/gl-security/product-security/product-security-engagements/product-security-requests/-/issues/new?description_template=infrasec-teleport) with Infrastructure Security.

## Architecture

The following diagram shows the Teleport architecture for GitLab infrastrucutre.
Some details are omitted for brevity.
Teleport resources, shown in green with Teleport icon, are not technically part of any Google Cloud projects.

![Click on the image to see the image in full size](./images/teleport-arch.png "GitLab Teleport Architecture")
