# KubeContainersWaitingInError

## Overview

More than 50% of the containers waiting to start for a deployment are waiting due
to reasons that we consider to be an error state (that is, any reason other than
`ContainerCreating`).

There are many reasons why containers will fail to start, but some include:

1. GCP Quota Limits: we are unable to increase the capacity of a node pool.
2. A configuration error has been pushed to the application, resulting in a termination during startup and a `CrashLoopBackOff`.
3. Kubernetes is unable to pull the required image from the registry
4. An increase in the amount of containers that need to be created during a deployment.
5. Calico-typha pods have undergone a recent migration/failure (see below)

When this alert fires, it means that new containers are not spinning up correctly.
If existing containers are still running, it does not necessarily indicate an outage,
but could lead to one if the existing containers are removed while in this state.

When this alert fires, the recipient should determine why the containers are failing to start.
The most efficient way to do this is to connect to the cluster and look at the state of the
failed pods, then check the events and logs to see what is causing them to be in that state.

## Services

- [kube Service Overview](../kubernetes.md)
- Owner: [Runway](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/team/runway/)

## Metrics

- [Container Waiting Reasons](https://dashboards.gitlab.net/d/alerts-kube_containers_waiting/alerts3a-containers-waiting?orgId=1) shows reasons why containers are waiting to start
- This chart indicates a saturation threshold of how many containers are stuck in a state where they are not Running. The count isn't really meaningful, but rather just indicates the source of this alert.
- This was added as a precaution to capture problems before they became big problems.  Ideally our clusters and configurations are Pods are solid such that this problem does not occur.
- Under normal circumstances, we'll see spikes of Pods cycle through `Pending` and `PodInitializing`.  These spikes are normal when major changes happen, such as an upgrade or config change, or anything else that would cause a whole set of Pods to be rotated out.  The length of time a Pod spends in either of these states should be short as we've optimized how our Pods start.  This may not be true for workloads that we do not own the source code too.
- [Dashboard example of the alert firing](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8714#note_1351307313)
- It is normal for there to be some indicators in the dashboard of pods cycling out of the desired state. When this alert fires, you will notice that the indicators stay above 50% on the graph. Once things recover, those metrics will come back below 50% (and preferably to 0 for the containers in question)

## Alert Behavior

- Unless something is catestrophic or a known issue happening, I would shy away from alert silencing.  If we do need to silence, make an attempt to target the smallest object possible, such as the deployment name, or if the problem is cluster wide, the target cluster, for example.
- This alert should be rare, and indicates a problem which will likely need manual attention
- [Dashboard example of the alert firing](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8714#note_1351307313)

## Severities

- Start with a low severity until we determine what impact this has on the target service that is showing disruption.  Example, if consul can't start, this is probably outage inducing.  But if sidekiq can't start, our PDB is around to ensure old pods are stuck around while we wait for whatever the blocker is to be repaired.  Sidekiq would still be functional.  Additional observation would be required for the impacted service.
- This alert will impact different sets of users depending on which pods are causing it. We will need to determine that before we will know whether the impact is internal or external

## Verification

- [Prometheus query that triggered the alert](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22r4f%22:%7B%22datasource%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22sum%20by%20%28type,%20env,%20tier,%20stage,%20cluster%29%20%28kube_pod_container_status_waiting_reason:labeled%7Breason%21%3D%5C%22ContainerCreating%5C%22,stage%21%3D%5C%22%5C%22,type%21%3D%5C%22%5C%22%7D%29%3E0%20%3E%3D%20on%20%28type,%20env,%20tier,%20stage,cluster%29%20%28topk%20by%20%28type,evn,tier,stage,cluster%29%20%281,%20kube_deployment_spec_strategy_rollingupdate_max_surge:labeled%7Bstage%21%3D%5C%22%5C%22,tier%21%3D%5C%22%5C%22,type%21%3D%5C%22%5C%22%7D%29%2A0.5%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
- [Alerts: Containers Waiting Dashboard](https://dashboards.gitlab.net/d/alerts-kube_containers_waiting/alerts3a-containers-waiting?orgId=1&var-PROMETHEUS_DS=e58c2f51-20f8-4f4b-ad48-2968782ca7d6&var-environment=gprd&var-type=web&var-stage=main&var-cluster=gprd-us-east1-b)
- We suck in events into Kibana, these would be our GKE events log.  We do not filter them out, so the same information can also be found in Stackdriver.  If using Stackdriver, it's easier to look for the impacted workload/cluster and find the link to logs from GCP's console first.  It helps create a filter query when troubleshooting from this direction.

## Recent changes

- [Recent related production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=change%3A%3Acomplete)
- [Recent helm MR's](https://gitlab.com/groups/gitlab-com/gl-infra/k8s-workloads/-/merge_requests?scope=all&state=merged)
- To roll back a change, find the MR which introduced it. The MR is likely to be in the [Kubernetes Workloads](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads) namespace. Revert that MR and make sure the pipeline completes.

## Troubleshooting

- Basic troubleshooting order
  - Connect to the cluster in quetsion
  - Identify the failing containers
  - Determine why they are failing
  - That should lead to what needs to be fixed to get the containers into a `Running` state
- On the [Alerts: Containers Waiting Dashboard](https://dashboards.gitlab.net/d/alerts-kube_containers_waiting/alerts3a-containers-waiting?orgId=1&var-PROMETHEUS_DS=e58c2f51-20f8-4f4b-ad48-2968782ca7d6&var-environment=gprd&var-type=web&var-stage=main&var-cluster=gprd-us-east1-b) select the `environment`, `type`, and `cluster` in question and see what the metrics look like there
- Useful scripts or commands
  - `glsh kube use-cluster gprd` Set up the cluster connection
  - `kubectl get pods -o jsonpath='{range .items[?(@.status.containerStatuses[-1:].state.waiting)]}{.metadata.name}: {@.status.containerStatuses[*].state.waiting.reason}{"\n"}{end}' -A` view the pods that are not running.
  - `kubectl get pods -A | grep -v "Running"` same as above but less correct and more information
  - `kubectl logs -n (namespace) (podname)` View the logs of a container identified with the previous commands
  - `kube describe pod -n (namespace (podname)` View the events and other information for a container identified with the previous commands

This PromQL query will show which deployments are out of their desired states:

```promql
sum by (type, env, tier, stage, cluster) (kube_pod_container_status_waiting_reason:labeled{reason!="ContainerCreating",stage!="",type!=""})>0 >= on (type, env, tier, stage,cluster) (topk by (type,evn,tier,stage,cluster) (1, kube_deployment_spec_strategy_rollingupdate_max_surge:labeled{stage!="",tier!="",type!=""})*0.5)
```

## Possible Resolutions

- [Previous incidents for this alert](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=a%3AKubeContainersWaitingInError&first_page_size=20)
- [2023-09-25: KubeContainersWaitingInError for canary services](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/16430)
- [2024-05-23: Containers are unable to start](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18057)
- [2024-03-20: KubeContainersWaitingInError external-dns](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/17739)

## Dependencies

- Kubernetes configuration or secret changes have historically caused the most alerts
- Secret configuration has been the primary violator
- The alert can fire if a container image can't be pulled
- PVC mounting

## Escalation

- It should be fairly straightforward to identify the deployment causing the problem. Once identified, it will be more clear as to where to escalate.  The Runway or delivery team are most likley to be able to help, but it will be more clear once we know the source of the alert.
- Slack channels where help is likely to be found: `#g_runway`

## Definitions

- [Link to the definition of this alert for review and tuning](/libsonnet/alerts/kube-cause-alerts.libsonnet)
- The only tunable parameter in the alert is the percentage of errored containers that we tolerate
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/kube/alerts/KubeContainersWaitingInError.md?ref_type=heads)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md?ref_type=heads)

## Related Links

- [Related alerts](./)
- [Related documentation](../kubernetes.md)
