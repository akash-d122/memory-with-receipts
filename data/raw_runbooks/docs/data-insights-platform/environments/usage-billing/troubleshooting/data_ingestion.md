# Troubleshooting: Usage Billing - Data Ingestion

For Data Insights Platform (DIP) deployments, we use [`metrics-catalog`](/metrics-catalog/services/data-insights-platform.jsonnet) to setup & manage our `Ingester` SLIs.

This setup provides us a few alert-definitions automatically - which can be sent to our engineers on-call. Following are alert-specific details of how to approach these alerts if & when you receive them.

## No data received OR Increased error rates

* Begin with our [main dashboard for Usage Billing](https://dashboards.gitlab.net/goto/ff3skeg290veof?orgId=1).
* Look for key signals in the __Throughput__ panel:
  * Requests: Do we have non-zero requests being received?
  * Errors: Do we have non-zero errors being generated?
  * Ingestion latency: Is the trend abnormal over a larger time period?

> While we do _not_ alert on ingestion latency yet, an increase from the baseline can be symptomatic of other issues in the system, e.g. resource starvation on DIP pods, NATS being unavailable, etc.

* If we don't see incoming requests, check with upstream sources of this traffic first.
  * In the current iteration, all traffic comes from `AI-gateway`. Check [AI-gateway dashboard(s)](https://dashboards.gitlab.net/goto/ff3vvjsjqqtxcd?orgId=1).
  * All requests are proxied via Cloudflare, ensure we're not rejecting traffic at that level. Check [Cloudflare dashboard(s)](TODO)
    * For details around configured Cloudflare zones/hosts, refer to the [configuration overview](../overview.md).
  * Our ingress endpoints have `rate-limits` on them, ensure they have not been updated recently and/or are causing traffic to be rate-limited. This is also done via Cloudflare and can be monitored on the aforementioned Cloudflare dashboards. These rate-limits are provisioned via the `config-mgmt` repository [here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/prdsub/gke-dip-ingress.tf?ref_type=heads).

* If we see an uptick in errors being generated.
  * Check logs for the concerned environment to ascertain the nature of these failures. [Kibana](https://log.gprd.gitlab.net/app/r/s/ce9Be)
  * Since ingesters only ever write data into NATS, ensure NATS is healthy.
    * [NATS - Usage Billing Dashboard](https://dashboards.gitlab.net/goto/bf3vvzt0dcu0we?orgId=1)
    * [NATS - Runbooks](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/nats?ref_type=heads)
  * If you see connection-specific issues, it should be okay to rolling restart the DIP `Statefulset`.

```text
➜  ~ kubectl -n data-insights-platform rollout restart sts data-insights-platform-single
statefulset.apps/data-insights-platform-single restarted
```

> Outside of NATS, ingested events can be malformed and/or not compliant with [Usage Billing data schemas](https://gitlab.com/gitlab-org/iglu/-/blob/master/public/schemas/com.gitlab/billable_usage/jsonschema/1-0-1?ref_type=heads). This class of errors will show up on this [graph](https://dashboards.gitlab.net/goto/bf3vw7apay8zke?orgId=1). If this is what's happening, involve folks from Analytics Instrumentation or AI Gateway teams.

* If we see ingestion latency trending upwards and/or has diverged from normal
  * Check resource consumption on the DIP pods, are they being starved?
    * [Data Insights Platform - Usage Billing Dashboard](https://dashboards.gitlab.net/goto/ff3skeg290veof?orgId=1) > check __Consumption__ panel.
  * Are these pods running out of memory consistently?
  * Are we not able to write to NATS fast enough?
    * This should be evident from the `ingester` pods, with requests timing out during writes to NATS. Check aforementioned logs.
  * __Solution__: See if vertically or horizontally scaling the `statefulset` helps.

## GKE setup on CustomerDot environments - `stgsub` & `prdsub`

* Ensure you have access to `NordVPN`, see [this](/docs/kube/k8s-oncall-setup.md#kubernetes-api-access) for more details.

* Ensure you can connect to the two environments as necessary, e.g. for `prdsub`, run the following when connected to a NordVPN gateway:

```text
➜  ~ glsh kube use-cluster prdsub --no-proxy
Switched to context "gke_gitlab-subscriptions-prod_us-east1_prdsub-customers-gke".
```

* Data Insights Platform is setup in the `Single` mode via a `Statefulset`.

> `Single` mode is when we deploy all DIP components in a single pod, so `ingesters`, `enricher`, `billing-exporter` all running as separate processes within the same pod.

```text
➜  ~ kubectl -n data-insights-platform get sts data-insights-platform-single
NAME                            READY   AGE
data-insights-platform-single   3/3     34d
➜  ~ kubectl -n data-insights-platform get pods
NAME                                                              READY   STATUS    RESTARTS       AGE
data-insights-platform-ingress-nginx-controller-6765bdc6964r2t7   1/1     Running   0              2d4h
data-insights-platform-single-0                                   1/1     Running   0              2d3h
data-insights-platform-single-1                                   1/1     Running   2 (2d3h ago)   2d3h
data-insights-platform-single-2                                   1/1     Running   1 (2d3h ago)   2d3h
```

* Check if the application container has enough resources allocated

```text
➜  ~ kubectl -n data-insights-platform get sts data-insights-platform-single -o json | jq -r '.spec.template.spec.containers[].resources'
{
  "limits": {
    "cpu": "2",
    "memory": "2Gi"
  },
  "requests": {
    "cpu": "250m",
    "memory": "1Gi"
  }
}
```
