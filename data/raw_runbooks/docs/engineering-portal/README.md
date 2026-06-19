<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Engineering Portal Service

* [Service Overview](https://dashboards.gitlab.net/d/engineering-portal-main/engineering-portal-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22engineering-portal%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::EngineeringPortal"

## Logging

* [stackdriver](https://cloudlogging.app.goo.gl/VxaeYiShZwJN9i1Z7)

<!-- END_MARKER -->

## Summary

Engineering Portal that provides a single pane of glass for a centralized software catalog with ownership and metadata.

> [!warning]
> **Not ready for `production` use.**

Engineering Portal is considered an [Experiment](https://docs.gitlab.com/policy/development_stages_support/#experiment). The purpose of adding PoC to runbooks during experimental status is to facilitate production readiness in the near future.

## Architecture

For architecture, refer to Engineering Portal PoC [documentation](https://gitlab.com/gitlab-com/gl-infra/engineering-portal-poc/-/blob/main/README.md#architecture).

## Performance

N/A for Experimental PoC.

## Scalability

For scalability, refer to Runway [documentation](https://docs.runway.gitlab.com/runtimes/cloud-run/scalability/) and Runway [service manifest](https://gitlab.com/gitlab-com/gl-infra/engineering-portal-poc/-/tree/main/.runway?ref_type=heads).

## Availability

N/A for Experimental PoC.

## Durability

N/A for Experimental PoC.

## Security/Compliance

For security, refer to (in progress) InfraSec [lightweight review](https://gitlab.com/gitlab-com/gl-security/product-security/infrastructure-security/bau/-/issues/15463).

## Monitoring/Alerting

For monitoring/alerting, refer to Runway [documentation](https://docs.runway.gitlab.com/reference/observability/#alerts) and Runway [archetype](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/engineering-portal-poc.jsonnet?ref_type=heads).

## Links to further Documentation

### Rotating OAuth Credentials

For rotating secrets, refer to Runway [documentation](https://docs.runway.gitlab.com/runtimes/cloud-run/secrets-management/#rotating-a-secret) and Runway [service secrets path](https://vault.gitlab.net/ui/vault/secrets/runway/kv/list/env/staging/service/portal-poc/).
