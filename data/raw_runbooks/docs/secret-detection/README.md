<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Detects secret leaks in the given payloads Service

* [Service Overview](https://dashboards.gitlab.net/d/secret-detection-main/secret-detection3a-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22secret-detection%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::SecretDetection"

## Logging

* [secret-detection](https://console.cloud.google.com/run/detail/us-east1/secret-detection/logs?project=gitlab-runway-production)

<!-- END_MARKER -->

## Summary

The Secret Detection Service is stateless service that scans for secret leaks in the given payload. This service is currently used by "Secret Push Protection" feature, and is maintained by the AST:Secret Detection team.

The service deployments are being [managed by Runway](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/secret_detection/decisions/005_use_runway_for_deployment/) and the service is privately accessible to Rails monolith (via internal load balancer).

The source code repository for the service is available [here](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-detection-service) and the runway deployment configuration is located [here](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-detection-service/-/blob/a1e8d90a324c99d5dbc48c8d1f580aa861791f74/.runway/runway.yml).

## Architecture

Architecture document is available [here](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/secret_detection/decisions/004_secret_detection_scanner_service/)

## Performance

Standalone benchmarks are available [here](https://gitlab.com/gitlab-org/gitlab/-/work_items/468107)

## Scalability

Secret Detection service is deployed using Runway and its scaling is handled by Cloud Run and configured as part of Runway deployment (see [documentation](https://docs.runway.gitlab.com/runtimes/cloud-run/scalability/)).

## Availability

As Secret Detection service is privately accessible only by Rails monolith, we are deploying the service only at the regions where Rails monolith is deployed. So, the service is currently deployed only at `us-east1` region.

## Security/Compliance

The service is stateless by nature and it doesn't log/store any customer-related data. Application Security review issue is available [here](https://gitlab.com/gitlab-com/gl-security/product-security/appsec/appsec-reviews/-/issues/238).

## Monitoring/Alerting

The service is deployed using Runway and Runway packs built-in observability, particularly [monitoring stack](https://docs.runway.gitlab.com/reference/observability/). Default Runway metrics for the service is available at [Runway Service Metrics dashboard](https://dashboards.gitlab.net/d/runway-service/runway3a-runway-service-metrics).

## Links to further Documentation

* [Documentation](https://gitlab.com/gitlab-org/security-products/secret-detection/secret-detection-service/-/blob/vbhat/resource-size/README.md)
* [Issue](https://gitlab.com/groups/gitlab-org/-/epics/13792)
