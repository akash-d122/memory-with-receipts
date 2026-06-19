# Rebuilding a GKE cluster

> [!note]
> This runbook covers the **replacement** of a zonal GKE cluster. If you seek
> to create a new cluster on a different region/zone, please refer to the
> [create new GKE cluster runbook](/k8s-new-cluster.md).

> [!important]
> The rebuild of a GKE cluster in staging or production **must** be done through of a [Change Request](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/), with approval from Sr. Infrastructure Managers and Release Managers.

## 1. Skip cluster deployments

It's necessary to skip deploying to the cluster while replacing it, this way we
don't disrupt the Auto Deploy.

1. Make sure the [Auto Deploy pipeline](https://ops.gitlab.net/gitlab-com/gl-infra/deployer/-/pipelines)
   is not active and no active deployment is happening for the targeted
   environment.
2. Identify the name of the cluster we need to skip, we need to use the full
   name of the GKE cluster, for example `gstg-us-east1-b`.
3. Set the variable `CLUSTER_SKIP` to the name of the cluster,
   `gstg-us-east1-b` for instance, in the [`ops` mirror CI variables](https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/settings/ci_cd),
   from which deployment pipelines are run.

> [!important]
> Do not forget to remove the variable after the maintenance window closes and
> the cluster is replaced.

## 2. Pause monitoring

Create silences on [alerts.gitlab.net](https://alerts.gitlab.net/) using the following example filters:

- `env="gstg" cluster="gstg-us-east1-b"`
- `env="gstg" region="us-east1-b" alert_class="traffic_cessation"`

## 3. Disable traffic to the cluster

All HAProxy nodes in the zone need to be stopped to disable all traffic to the zonal cluster in a timely manner while also not over-saturating Canary, as it doesn't have the capacity to handle the full main stage traffic of a single zone.

This will trigger a graceful stop of all HAProxy nodes in the zone with a forced stop after 5 minutes, 5 at a time with a 1 minute pause after each one:

```sh
knife ssh -C 5 'chef_environment:gstg AND roles:gstg-base-haproxy AND zone:projects\/65580314219\/zones\/us-east1-b' \
  'sudo systemctl mask haproxy.service; sudo systemctl kill --signal SIGUSR1 haproxy.service; while [ $(systemctl is-active haproxy.service) != "inactive" ] && [ ${i:=1} -lt 150 ]; do sleep 2; i=$((i + 1)); done; sudo systemctl stop haproxy.service; systemctl status haproxy.service; sleep 60'
```

> [!note]
> `SIGUSR1` signals HAProxy to stop listening for new connections and let all current connections finish normally before exiting. The default stop signal in `haproxy.service` is `SIGTERM` which would close all connections immediately, so we can't simply use `systemctl stop haproxy.service` here.

## 4. Replace the GKE cluster

### 4.a. Terraform

This is a two step process: the first one to replace the cluster and node
pools, then the next to update the Kubernetes authentication method and secret
engine in Vault with the new cluster IP and CA certificate.

1. Open a new merge request with the desired changes to the zonal GKE cluster ([example MR](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/11519)).
   If the cluster is to be rebuilt without changes, add a comment in the
   environment's Terraform configuration.

2. Get approval for the merge request but do not merge it yet.

3. Perform a `terraform plan` via Atlantis in the targeted environment to
   recreate the cluster by commenting in the MR:

   ```sh
   atlantis plan -p gstg -- -replace module.gke-us-east1-b.google_container_cluster.cluster
   ```

   You should see something like:

   ```
   Terraform will perform the following actions:

     # module.gke-us-east1-b.google_container_cluster.cluster will be replaced, as requested

   ...

     # module.gke-us-east1-b.google_container_node_pool.node_pool["generic-1"] will be replaced due to changes in replace_triggered_by
   ```

4. Then `apply` **without automerging** by commenting in the MR:

   ```sh
   atlantis apply -p gstg --auto-merge-disabled
   ```

   > [!note]
   > This should take around 20 to 30 minutes.

   Once applied, the new cluster and all its node pools should be up.

5. Perform a `terraform plan` via Atlantis in the `vault-production`
   environment to update the Kubernetes authentication method and secret engine
   by commenting in the MR:

   ```sh
   atlantis plan -p vault-production
   ```

6. Then `apply` by commenting in the MR:

   ```sh
   atlantis apply -p vault-production
   ```

   Once applied, Atlantis will merge the MR automatically.

### 4.b. New cluster configuration setup

At this point we have a brand new cluster and we need to orient our tooling to
use it.

1. [Install `glsh`](https://gitlab.com/gitlab-com/runbooks#running-helper-scripts-from-runbook) if it's not installed already.
1. Run `glsh kube setup` to setup `kubectl` with the new cluster configuration.
2. Validate we can use the new context and `kubectl` works with the cluster:

   ```sh
   glsh kube setup
   glsh kube use-cluster gstg-us-east1-b
   kubectl get pods --all-namespaces
   ```

3. Create a new JWT token to re-enable authentication to the cluster via Vault:

    1. Verify in [ArgoCD](https://argocd.gitlab.net/) that [`vault-k8s-secrets`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/vault-k8s-secrets) has been reinstalled on the cluster.

    2. Get the new JWT token that was just provisioned with the release and
       save it into Vault:

    ```sh
    kubectl --namespace vault-k8s-secrets get secret vault-k8s-secrets-token -o jsonpath='{.data.token}' | base64 -d | \
        vault kv put ci/ops-gitlab-net/gitlab-com/gl-infra/config-mgmt/vault-production/kubernetes/clusters/gstg/gstg-us-east1-b service_account_jwt=-
    ```

    3. [Trigger a new `config-mgmt` pipeline for the `vault-production` environment](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/pipelines/new?ref=main&var[ENV]=vault-production)
       to update the Kubernetes secrets engine with this new JWT token.

## 4.c. Deploy all workloads

1. Then let ArgoCD deploy all workloads to the rebuilt cluster:

   1. Confirm the cluster Secret in [`argocd/config`](https://gitlab.com/gitlab-com/gl-infra/argocd/config)
      still exists and has the expected labels (e.g. `gitlab.com/environment`,
      `gitlab.com/k8s-cluster-name`); the ArgoCD ApplicationSets use these
      labels to fan applications out to clusters.
   2. From the [ArgoCD UI](https://argocd.gitlab.net/), filter applications by
      the rebuilt cluster and trigger a sync on any that are not already
      converging. Most applications will sync automatically once the cluster
      is reachable.
   3. After ArgoCD reports the applications as `Healthy`, run
      `kubectl get pods --all-namespaces` against the cluster and check that
      all workloads are working correctly before going to the next step.

### 4.d. Deploy `gitlab-com`

1. Remove the `CLUSTER_SKIP` variable from the [`ops` mirror CI variables](https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/settings/ci_cd).
2. Find the latest pipeline which performed a configuration change to the
   targeted environment and re-run the job associated with the rebuilt cluster.

   > [!important]
   > This will install all releases and configurations but will not deploy the
   > correct version of GitLab, that comes in the following step

   > [!tip]
   > It'll be easiest to find a pipeline from the [most recent merged MR](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests/?sort=merged_at_desc&state=merged&first_page_size=20)
   > rather than browsing through the pipeline pages

3. Deploy the correct version of GitLab by running the latest successful `auto-deploy` job:

   1. Go to the [`#announcements` channel](https://gitlab.slack.com/archives/C8PKBH3M5) and check the latest successful job for the targeted environment.
   2. Re-run the Kubernetes job for the targeted cluster.

4. Spot check the cluster to validate that all pods are coming online and remain in a running state:

   ```sh
   glsh kube use-cluster gstg-us-east1-b
   kubectl get pods --namespace gitlab
   ```

5. Verify that we run the same version of GitLab on all clusters:

   ```sh
   glsh kube use-cluster gstg-us-east1-b
   kubectl get configmap --namespace gitlab gitlab-gitlab-chart-info -o jsonpath="{.data.gitlabVersion}"
   glsh kube use-cluster gstg-us-east1-c
   kubectl get configmap --namespace gitlab gitlab-gitlab-chart-info -o jsonpath="{.data.gitlabVersion}"
   ```

   The version from both clusters should match.

## 5. Resume monitoring

1. In [this dashboard](https://dashboards.gitlab.net/goto/1G_u458NR?orgId=1) we
   should see the numbers of the pods and containers of the cluster.
2. Remove any silences that were created earlier.
3. Validate that no alerts are firing related to this replacement cluster in [Alertmanager](https://alerts.gitlab.net).

## 6. Re-enable traffic to the cluster

We now need to restart all HAProxy nodes to re-enable traffic to the cluster.

We want to start them 1 at a time with a 1 minute pause between each one to give the cluster some time to scale up so that we don't over-saturate it:

```sh
knife ssh -C 1 'chef_environment:gstg AND roles:gstg-base-haproxy AND zone:projects\/65580314219\/zones\/us-east1-b' \
  'sudo systemctl unmask haproxy.service; sudo systemctl start haproxy.service; sleep 60'
```
