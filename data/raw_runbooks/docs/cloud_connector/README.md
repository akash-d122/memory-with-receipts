<!-- Permit linking to GitLab docs and issues -->
<!-- markdownlint-disable MD034 -->
# Cloud Connector

Cloud Connector is a way to access services common to multiple GitLab deployments, instances, and cells.
Cloud Connector is not a dedicated service itself, but rather a collection of APIs, code and configuration
that standardize the approach to authentication and authorization when integrating Cloud services with a GitLab instance.

This document contains general information on how Cloud Connector components are configured and operated by GitLab Inc.
The intended audience is GitLab engineers and SREs who have to change configuration for or triage issues with these
components.

See [Cloud Connector architecture](https://docs.gitlab.com/ee/development/cloud_connector/architecture.html) for more information.

---

## Triage decision chart

Navigate the chart below to locate the system and owner of the failing endpoints. The chart covers the AI gateway integration
with Cloud Connector specifically, as it is the system with the most usage, but translates to other backends too:

```mermaid
flowchart LR
    start(Error code received) -- 401 --> is401
    is401{Who sent it?} -- gitlab-rails --> duo_triage1(MAY be a Cloud Connector issue. Consult duo/triage.md.\nEscalate to SSCS - Auth or Fulfillment - Provision as needed.)
    is401{Who sent it?} -- AIGW --> duo_triage2(MAY be a Cloud Connector issue. Consult duo/triage.md.\nEscalate to SSCS - Auth as needed.)

    start -- 403 --> is403
    is403{Who sent it?} -- gitlab-rails --> rails403(NOT a Cloud Connector issue. Consult duo/triage.md.)
    is403{Who sent it?} -- AIGW --> aigw403(MAY be a Cloud Connector issue.\nConsult duo/triage.md.\nEscalate to Fulfillment - Provision as needed.)

    start -- 429 --> is429
    is429{Who sent it?} -- gitlab-rails --> rails429(NOT a Cloud Connector issue.\nConsider increasing rate limit for endpoint.\nEscalate to respective stage group as needed.)
    is429{Who sent it?} -- Cloudflare --> cf429(MAY be a Cloud Connector issue.\nConsider increasing rate limit for user/IP.\nEscalate to Runway group as needed.)

    start -- 500 --> is500
    is500{Who sent it?} -- gitlab-rails --> rails500(MAY be a Cloud Connector issue.\nIsolate cause of crash and escalate as needed.)
    is500{Who sent it?} -- AIGW --> aigw500(MAY be a Cloud Connector issue.\nIsolate cause of crash and escalate as needed.)

    start -- 502/503 --> is502(NOT a Cloud Connector issue.\nThe origin is unavailable.\nEscalate to service owner.)

    start -- 522 --> cf522(MAY be a Cloud Connector issue.\nCloudflare sends this code\nwhen the origin times out. Escalate to Runway group.)
```

For client errors with AI features, consult the [Duo triage runbook](../duo/triage.md).

## Cloudflare

See [Cloud Connector - Cloudflare](./cloudflare.md).

Applies to all edges in the triage chart that are labeled Cloudflare.

## Authentication

See [Cloud Connector - Authentication](../sscs/auth/cloud-connector.md).

Applies to all cases in the triage chart that render authn/authz codes (401, 403).

<!-- markdownlint-enable MD034 -->
