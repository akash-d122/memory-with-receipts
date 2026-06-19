<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Secret Revocation Service

* [Service Overview](https://dashboards.gitlab.net/d/runway-service/runway3a-runway-service-metrics)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22secret-revocation%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::SecretRevocation"

## Logging

* [secret-revocation](https://console.cloud.google.com/run/detail/us-east1/secret-revocation/logs?project=gitlab-runway-production)

<!-- END_MARKER -->

## Summary

Secret Revocation (`secret-revocation`) is a Runway-based workload/deployment that is a part of the [Secret Revocation Service](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service).

It runs the service in the API (default) mode, and serves a number of [API endpoints](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service#api) that are used by the [monolith](https://gitlab.com/gitlab-org/gitlab) to inform partner APIs of leaked tokens to revoke. When a token is received, the appropriate handler is identified, and message is created and published to the corresponding [Google PubSub topic](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service#pubsub_topic), which are then picked up the [Worker workload](../secret-revc-worker/README.md) to send the actual revocation requests to partner APIs.

This service is currently used by ["Automatic Response to Leaked Secrets"](https://docs.gitlab.com/user/application_security/secret_detection/automatic_response) feature, and is maintained by the AST:Secret Detection team.

The source code repository for both services (API and Worker) is available [here](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service) and the runway deployment configuration are located in:

* [`secret-revc-worker`](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service/-/tree/main/.runway/secret-revc-worker)
* [`secret-revocation`](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service/-/tree/main/.runway/secret-revocation)

## Architecture

Check the [documentation](https://docs.gitlab.com/user/application_security/secret_detection/automatic_response/#high-level-architecture) for a high-level architecture.

More details about the end-to-end workflow can also be found [here](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service#workflow).

<!-- ## Performance -->

## Scalability

This service is deployed using Runway and its scaling is handled by Cloud Run and configured as part of Runway deployment (see [documentation](https://docs.runway.gitlab.com/runtimes/cloud-run/scalability/)).

## Availability

Both workloads are [publicly accessible](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service#public-availability) because each require some [external interaction](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service#external-interactions) whether ingress or egress. They're deployed in `us-east1` region.

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

The service is deployed using Runway and Runway packs built-in observability, particularly [monitoring stack](https://docs.runway.gitlab.com/reference/observability/). Default Runway metrics for the service is available at [Runway Service Metrics dashboard](https://dashboards.gitlab.net/d/runway-service/runway3a-runway-service-metrics).

## Links to further Documentation

* [Documentation](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-revocation-service/-/blob/main/README.md)

### Old Service (SecAuto)

* [Source Code and Docker Images](https://gitlab.com/gitlab-com/gl-security/engineering-and-research/automation-team/secret-revocation-service)
* [Configuration and Deployment](https://gitlab.com/gitlab-private/gl-security/engineering-and-research/automation-team/kubernetes/secauto/secret-revocation-service)
* [Terraform GCP Resources](https://gitlab.com/gitlab-com/gl-security/engineering-and-research/automation-team/terraform/-/blob/main/secauto-live/svc-srs.tf)

### New Service (AST:Secret Detection / on Runway)

* [Original Issue](https://gitlab.com/gitlab-org/gitlab/-/issues/481589)
* [Transition SRS to AST:Secret Detection (and Runway)](https://gitlab.com/groups/gitlab-org/-/epics/18159):
  * [Runway Transition](https://gitlab.com/groups/gitlab-org/-/epics/18160)
  * [New Service Rollout](https://gitlab.com/groups/gitlab-org/-/epics/18161)
  * [Old Service Cleanup](https://gitlab.com/groups/gitlab-org/-/epics/18162)
