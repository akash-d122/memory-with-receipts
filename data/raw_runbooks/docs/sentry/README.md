<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Monitoring Service

* [Service Overview](https://dashboards.gitlab.net/d/sentry-main/sentry-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22sentry%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Sentry"

## Logging

* [system](https://log.gprd.gitlab.net/goto/b4618f79f80f44cb21a32623a275a0e6)

<!-- END_MARKER -->

## General

You can find Sentry's general documentation in the Observability team's [docs-hub](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/platform-design/sentry/overview).

## Architecture

A single VM node running the services needed for Sentry, mainly PostgreSQL, Redis Server, and Prometheus for monitoring.
