<!-- Permit linking to GitLab docs and issues -->
<!-- markdownlint-disable MD034 -->
# Cloud Connector - Authentication

Cloud Connector uses JSON Web Tokens to authenticate requests in backends. Our primary backend is AI Gateway. Therefore we use it in examples and links below.

For multi-tenant customers on gitlab.com, the Rails application issues and signs these tokens. For single-tenant customers (SM/Dedicated), CustomersDot issues
and signs these tokens.

To validate tokens, Cloud Connector backends fetch the corresponding keys from the gitlab.com
and CustomersDot Rails applications respectively.

When the customer request reaches our backend (routed from [Cloudflare](./cloudflare.md)), we need to authenticate it.
The code that performs auth is stored in a separate [gitlab-cloud-connector repo](https://gitlab.com/gitlab-org/cloud-connector/gitlab-cloud-connector/-/tree/main/src/python?ref_type=heads)
and injected into "cloud connected" backends via `gitlab-cloud-connector` [package](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/de68b8096120586a75474ffc698b940327de6066/pyproject.toml#L54).
We only support Python backends through this library, however, there are other Cloud Connector backends such as the SAST Scanner Service that perform similar tasks.

Refer to [JWKS fetch](./cloud-connector-jwks-keys-fetch.md) for in-depth JWKS fetch mechanism overview and potential failure modes.

## Alerts and troubleshooting

We maintain metrics and alerts for the following areas:

- **AI gateway key fetches:**: Refer to [AiGatewayJwksFetchFailed](./alerts/AiGatewayJwksFetchFailed.md) to understand when
  the alert is sent and how to troubleshoot.
- **AI gateway 401/403 errors:** Use the [Duo triage runbook](../duo/triage.md) to troubleshoot.
- **Performance issues with minting tokens on gitlab.com:** Turn to the following dashboards for troubleshooting:
  - [Token creation sec/sec (real)](https://dashboards.gitlab.net/goto/L1rytilNR?orgId=1)
  - [Tokens issued / sec](https://dashboards.gitlab.net/goto/jC4XpilHR?orgId=1)
  - [Code Suggestions time spent in Rails / sec (proxy metric)](https://log.gprd.gitlab.net/app/r/s/pnBfK)

## Key rotation

Keys should be rotated on a 6 month schedule both in staging and production.

### Rotating keys for gitlab.com

Do not start key rotation if there is an active JWKS-related [incident](./alerts/AiGatewayJwksFetchFailed.md).

Keys must be rotated in staging and production. The general steps in both environments are:

1. Run `sudo gitlab-rake cloud_connector:keys:list` to verify there is exactly one key.
1. Run `sudo gitlab-rake cloud_connector:keys:create` to add a new key to rotate to.
1. Run `sudo gitlab-rake cloud_connector:keys:list` to verify there are exactly two keys.
1. Ensure validators have fetched the new key via OIDC Discovery. Since keys are cached both in HTTP
   caches and application-specific caches, this may require waiting at least 24 hours for these
   caches to expire. This process can be expedited by:
   - Restarting/redeploying backend services to evice their in-memory caches.
   - [Purging HTTP caches in Cloudflare](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/gitlab.com/caching/configuration)
     for the `/oauth/discovery/keys` endpoint.
1. For the AI Gateway only, ensure [this dashboard](https://log.gprd.gitlab.net/app/r/s/p7Rhe) shows no events.
1. Run `sudo gitlab-rake cloud_connector:keys:rotate` to swap current key with new key, enacting the rotation.
1. Monitor affected systems:
   - Ensure Puma and Sidekiq processes have swapped to the new key. This may take some time due keys being cached
     in process memory.
     - [Puma key load events](https://log.gprd.gitlab.net/app/r/s/4tqY3)
     - [Sidekiq key load events](https://log.gprd.gitlab.net/app/r/s/s2iae)
   - Ensure all Puma and Sidekiq workers are now [using the new key to sign requests](https://dashboards.gitlab.net/goto/s7KShmhHg?orgId=1).
   - **Do not proceed with the process until:**
     1. Keys in use to sign requests have converged fully to the new key.
     1. Backends should not see elevated rates of `401 Unauthorized` responses.
1. Run `sudo gitlab-rake cloud_connector:keys:trim` to remove the now unused key.
1. Monitor affected systems as before to ensure the rotation was successful.

#### Rotating keys in staging

1. Run `/change declare` in Slack and create a C3 [Change Request](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/).
1. Teleport to `console-01-sv-gstg`.
1. Run steps outlined [above](#rotating-keys-for-gitlabcom).
1. Close the CR issue.

#### Rotating keys in production

1. Run `/change declare` in Slack and create a C2 [Change Request](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/).
1. Teleport to `console-01-sv-gprd`.
1. Run steps outlined [above](#rotating-keys-for-gitlabcom).
1. Close the CR issue.
1. Create a Slack reminder in `#g_cloud_connector` set to 6 months from now with a link to this runbook.

### Rotating keys for customers.gitlab.com

Follow instructions [here](https://gitlab.com/gitlab-org/customers-gitlab-com/-/blob/main/doc/security/jwk_signing_key_rotation.md).

<!-- markdownlint-enable MD034 -->
