<!-- Permit linking to GitLab docs and issues -->

# JWKS keys fetch for token-based Authentication

## About this page

This section provides in-depth overview JWKS fetch we perform in order to authenticate Cloud Connector requests.
It will help to understand better the impact of the JWKS sync issues we alert [in Slack](./alerts/AiGatewayJwksFetchFailed.md).
For the general overview, refer to the [main page](./README.md/#token-based-authentication).

## Why fetch JWKS?

Cloud Connector uses JSON Web Tokens to authenticate requests in backends.
For multi-tenant customers on gitlab.com, the Rails application issues and signs these tokens.
For single-tenant customers (SM/Dedicated), CustomersDot issues
and signs these tokens.

To validate these tokens, Cloud Connector backends need to fetch the corresponding keys from the gitlab.com
and CustomersDot Rails applications respectively.

Our primary "cloud connected" backend is AI Gateway.
Therefore we use it in explanations and code references below.

## When are JWKS fetched?

We perform the keys fetch multiple times during the AI Gateway's pod lifetime:

- While evaluating the readiness probe
- When a request is made and the cache from the previous fetch is expired or missing

### In Readiness probe

We fetch keys as a part of the `readiness` [probe](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/de68b8096120586a75474ffc698b940327de6066/ai_gateway/api/monitoring.py#L144).
That guarantees us that every instance of AI Gateway starts up with all required keys from all configured providers.
That also means that while CustomersDot or gitlab.com key endpoints are unavailable, we can't rotate AI Gateway pods.
If it continues for a longer period of time, that may lead to AI Gateway service degradation.

We log unsuccessful Cloud Connector key fetches during `readiness` probe with `json.jsonPayload.cloud_connector_ready : false`: [Elastic query for AI GW](https://log.gprd.gitlab.net/app/r/s/eQS2H).
We also log relevant errors which you can find in `logger : cloud_connector`.

Currently, we don't alert on `readiness` failures but we [plan](https://gitlab.com/gitlab-org/cloud-connector/gitlab-cloud-connector/-/issues/94) to improve that.

Note: we don't fetch Cloud Connector keys in the `readiness` probe while in the *Self-Hosted-Models* setup: [refer to this](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/blob/main/ai_gateway/api/monitoring.py?ref_type=heads#L148)

### During the pod lifetime

We always cache a combined keyset from all key providers as a single cache record.
Currently, the cache duration is [24 hours](https://gitlab.com/gitlab-org/cloud-connector/gitlab-cloud-connector/-/blob/main/src/python/gitlab_cloud_connector/providers.py?ref_type=heads#L89)
We need to re-fetch keys if:

- The cache is expired. Assuming we performed the `readiness` probe key fetch and cached it, that would mean that the pod was alive more than the cache duration. We plan to reduce the cache duration for simpler and swifter key rotations.
- If the cache is missing. It can happen if the backend does not run Cloud Connector keys fetch in `/readiness`.

In these cases, we re-fetch all keys synchronously during the request and then cache them.

## Keys fetch scenarios and failure modes

These are three potential outcomes of the keys fetch:

- Good: we are able to fetch all keys and we cached them. This is the expected behaviour.
- Attention needed: we failed to obtain keys from some providers, but we fall back to a cache.
  - That may be the result of gitlab.com or CustomersDot being down during that time. That typically means outage or other problem with the endpoint. We always retry the request. If that does not help, we re-cache the old keyset one more time (bump the cache expiry). In combination with the `readiness` key fetch, that guarantees us that we still operate with the full valid keyset (while it remains unchanged on the providers' side).
  - We should not proceed with key rotations if see these log events as some instances of AI Gateway would keep their "old" keys for longer
  - We log it with `"Old JWKS re-cached: some key providers failed"` message.
- Bad: we failed to fetch some keys, but we don't have a cache.
  - It shouldn't happen outside of the `readiness` check. When it happens in `readiness`, the pod will not serve requests and retry the check (and the key fetch) again later.
  - It means that we operate on a "partial" key set. For example: we fetched keys from gitlab.com, but failed to obtain them from CustomersDot. We will respond with `401` to every request signed with the token issued by CustomersDot.
  - We log it with `"Incomplete JWKS cached: some key providers failed, no old cache to fall back to"` message.

Note: We plan to improve error logging (in particular: cleaner messages/labels) under [this issue](https://gitlab.com/gitlab-org/cloud-connector/gitlab-cloud-connector/-/issues/92)
