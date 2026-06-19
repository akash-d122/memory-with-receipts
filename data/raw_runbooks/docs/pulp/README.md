<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Pulp (pulp.pre.gitlab.net) Service

* [Service Overview](https://dashboards.gitlab.net/d/pulp-main/pulp-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22pulp%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Pulp"

## Logging

* [Content](https://nonprod-log.gitlab.net/app/r/s/DuzJG)
* [API](https://nonprod-log.gitlab.net/app/r/s/2Bwu3)
* [Worker](https://nonprod-log.gitlab.net/app/r/s/9QcWy)
* [Pulp Operator](https://nonprod-log.gitlab.net/app/r/s/vYGex)
* [Ingress Controller - Application Logs](https://nonprod-log.gitlab.net/app/r/s/pHNy4)
* [Ingress Controller - Request Logs](https://nonprod-log.gitlab.net/app/r/s/oJ5FX)
* [SQL Proxy](https://nonprod-log.gitlab.net/app/r/s/6jXtT)

<!-- END_MARKER -->

## Documentation

* [Backup & Restore](./backup-restore.md)
* [User Management](./user-management.md)
* [Service Level Indicators (SLIs)](./pulp-slis.md)
* [Deleting a Package](./delete-package.md)

## Summary

Pulp is set up via:

* [Pulp terraform module to define GCP resources](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/applications/pulp)
* [Pulp terraform env config for the GCP resources](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/pre/pulp.tf)
* [Pulp Helm chart to define k8s resources](https://gitlab.com/gitlab-com/gl-infra/charts/-/tree/main/gitlab/pulp?ref_type=heads)
* [Pulp service in argocd/apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/pulp)

## Architecture

[Infrastructure Architecture overview](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/applications/pulp/-/blob/main/ARCHITECTURE.md?ref_type=heads)

## Pulp CLI

The Pulp CLI is a command-line interface for interacting with the Pulp service. It can be used for various administrative tasks, including user management, repository management, and content synchronization.

### Installation

Follow the [Pulp CLI installation guide](https://pulpproject.org/pulp-cli/docs/user/guides/installation/).

### Configuration

Before using the Pulp CLI, you need to configure it to connect to your Pulp instance. This typically involves setting the base URL, API root, and authentication credentials.

```bash
export PULP_ADMIN_PASSWORD=$(kubectl get secret pulp-custom-admin-password -o jsonpath='{.data.password}' | base64 -d)
export PULP_DOMAIN=<pulp-domain> # e.g., pulp.pre.gitlab.net

pulp config create \
  --base-url "https://${PULP_DOMAIN}" \
  --api-root "/pulp/" \
  --verify-ssl \
  --format json \
  --username admin \
  --password "${PULP_ADMIN_PASSWORD}" \
  --timeout 0
```

**Note**: Replace `<pulp-domain>` with the actual domain of your Pulp instance. The `PULP_ADMIN_PASSWORD` is retrieved from a Kubernetes secret, which assumes you have `kubectl` access to the cluster where Pulp is deployed.

### Basic Usage

Once configured, you can use the `pulp` command to interact with the service.

#### Checking Pulp Status

To verify that the CLI can connect to the Pulp instance and that the service is running:

```bash
pulp status
```

#### Listing Users

To list all users configured in Pulp:

```bash
pulp user list
```

#### Listing Roles

To list available roles for role-based access control (RBAC):

```bash
pulp role list
```

### Further Documentation

For more detailed information on specific CLI commands and use cases, refer to:

* [Pulp CLI Documentation](https://pulpproject.org/pulp-cli/)
* [Functional Operations](./functional-operations.md) (for general application configuration and usage)
* [User Management](./user-management.md) (for detailed user creation and permission management)
* [Backup & Restore](./backup-restore.md) (for backup and disaster recovery procedures)
* [Infrastructure Setup](./infrastructure-setup.md) (for deploying Pulp in new environments)
* [Troubleshooting](./troubleshooting.md) (for common issues and resolution steps)
* [Manage Repository Metadata Signing Keys](./manage-repository-metadata-signing-keys.md) (for GPG key management)
* [Cloudflare Worker Analytics Engine](./cloudflare-worker-analytics-engine.md) (for analytics and monitoring via Cloudflare Workers)
