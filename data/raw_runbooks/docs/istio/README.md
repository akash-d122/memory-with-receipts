<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Istio Service

* [Service Overview](https://dashboards.gitlab.net/d/istio-istio_control_plane/istio-istio-control-plane-dashboard)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22istio%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Istio"

## Logging

* [istiod (Control Plane)](https://dashboards.gitlab.net/goto/thvr5ISSR?orgId=1)
* [istio-gateway](https://dashboards.gitlab.net/goto/OAw6cISSR?orgId=1)
* [istio-internal-gateway](https://dashboards.gitlab.net/goto/IdERpIISR?orgId=1)
* [istio-cni-node](https://dashboards.gitlab.net/goto/sdWmpISSg?orgId=1)

<!-- END_MARKER -->

## Summary

[Istio](https://istio.io/latest/about/service-mesh/#what-is-istio) is an open platform-independent [service mesh](https://istio.io/latest/about/service-mesh/#what-is-a-service-mesh) that provides traffic management, policy enforcement, and telemetry collection.

Istio has two main components: the data plane and the control plane.

* The data plane is the communication between services. All traffic that mesh services send and receive (data plane traffic) is proxied through an Envoy proxy which is deployed along with each service that starts in the cluster, or runs alongside services running on VMs.
* The control plane (istiod) takes your desired configuration, and its view of the services, and dynamically programs the proxy servers, updating them as the rules or the environment changes.

## Configurations

Istio components are managed with the help of several Helm Charts. They are deployed using Flux and their definitions and configurations can be found on the repositories below.

* [Istio Components](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/components/-/tree/main/istio): Contains the definition for all Istio Helm Chart releases, namespace definition, as well as service and pod monitor definitions that are shared across all environments.
  * [Istio Base](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/components/-/blob/main/istio/base.yaml): Cluster Wide Resources and CRDs.
  * [IstioD](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/components/-/blob/main/istio/istiod.yaml): Istio Control Plane.
  * [Istio Gateway](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/components/-/blob/main/istio/istio-ingress.yaml): Helm release for the Public Istio Ingress Gateways.
  * [Istio Internal Gateway](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/components/-/blob/main/istio/istio-internal-ingress.yaml): Helm release for the Internal Istio Ingress Gateways.
  * [Istio CNI](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/components/-/blob/main/istio/cni.yaml) Helm Release for the Istio CNI plugin.

We use `overlays` on a per environment and cluster level using Flux `kustomizations`, to override helm chart values and create additional supporting manifest for the Istio deployments.

* [Istio - Ops Env Shared Overlay](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/tenants/reliability/-/tree/main/overlays/gke/gitlab-ops/shared/istio)
* [Istio - ops-gitlab-gke Cluster Overlay](https://gitlab.com/gitlab-com/gl-infra/k8s-mgmt/tenants/reliability/-/tree/main/overlays/gke/gitlab-ops/us-east1/ops-gitlab-gke/istio)

## Upgrade Procedure

Renovate will create an MR whenever there are updates available for the Istio Helm Charts. We have defined dependencies between all HelmRelease definitions in Flux, so after merging the Renovate MR all Istio components will be will be upgraded as follows:

 1. `istio-base`
 1. `istiod`
 1. Others: `istio-gateway`, `istio-internal-gateway`, `istio-cni`

### Upgrade Istio Gateways

The [istio/gateway Helm Chart](https://artifacthub.io/packages/helm/istio-official/gateway) doesn't replace the Gateway Deployment pods automatically. After the Renovate MR is merged and Flux has reconciled the changes, we need to execute a rolling restart of both `istio-gateway` and `istio-internal-gateway` Deployments.

```
# kubectl rollout restart deployments -n istio-ingress
```

You can monitor the upgrade procedure as follows:

* From your workstation using istioctl:

```
# watch -n 2 istioctl version
```

* Using Grafana dashboard [Istio Components by Version](https://dashboards.gitlab.net/d/istio-istio_mesh/istio3a-istio-mesh-dashboard?orgId=1&refresh=5m&viewPanel=111&var-datasource=default&var-environment=ops)

<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring/Alerting

### Istio Grafana Dashboards

* [Istio Control Plane Dashboard](https://dashboards.gitlab.net/d/istio-istio_control_plane/istio-istio-control-plane-dashboard)
* [Istio Mesh Dashboard](https://dashboards.gitlab.net/d/istio-istio_mesh/istio-istio-mesh-dashboard)
* [Istio Service Dashboard](https://dashboards.gitlab.net/d/istio-istio_service/istio-istio-service-dashboard)
* [Istio Workload Dashboard](https://dashboards.gitlab.net/d/istio-istio_workload/istio-istio-workload-dashboard)

### Istio Mesh Observability Tool - Kiali

* [gstg-gitlab-gke](https://kiali.gstg-gitlab-gke.us-east1.gitlab-staging-1.gke.gitlab.net/kiali)
* [gstg-us-east1-b](https://kiali.gstg-us-east1-b.us-east1-b.gitlab-staging-1.gke.gitlab.net/kiali)
* [gstg-us-east1-c](https://kiali.gstg-us-east1-c.us-east1-c.gitlab-staging-1.gke.gitlab.net/kiali)
* [gstg-us-east1-d](https://kiali.gstg-us-east1-d.us-east1-d.gitlab-staging-1.gke.gitlab.net/kiali)
* [ops-gitlab-gke](https://kiali.ops-gitlab-gke.us-east1.gitlab-ops.gke.gitlab.net/kiali)
* [ops-central](https://kiali.ops-central.us-central1.gitlab-ops.gke.gitlab.net/kiali)

<!-- ## Links to further Documentation -->
