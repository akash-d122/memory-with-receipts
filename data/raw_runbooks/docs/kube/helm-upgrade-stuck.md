# Helm Upgrade is Stuck

On the `k8s-workloads/gitlab-com` repository, [we ask that helm be the
maintainer for
operations](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/bc4d1c0b71668c679200ca282d5cd55a479837b2/bases/helmDefaults.yaml#L5).
This has a downside where if helm were to fail to talk to the Kubernetes API at
the right time, an upgrade will get stuck.

## Evidence

An auto-deploy will fail immediately with an error:

> `Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in
> progress`

## Information Gathering for Remediation

Ensure that no other pipelines are executing just in case we ran into an edge
case with resource locking and two CI jobs started executing against the same
cluster at the same time.  Remember that the jobs that run are located on our
ops instance.

Ensure that all deployments or objects have reconciled and that the cluster
isn't suffering some other failure.  What we want to avoid is attempting to fix
a problem that we make worse because the root cause is falsely identified.  The
easiest way to check for this is to ensure that all Deployments are up-to-date.
This can be done by printing the `.status` object of the Deployment, example,
`kubectl get deploy gitlab-gitlab-pages -o json | jq .status`.  Observe the
following:

* Conditions `Available` and `Progressing` to ensure their status is `True`.
* Ensure the number of `updatedReplicas` and `availableReplicas` matches or is
  at least very close
  * Mind that with HPA's these values may differ by a tiny amount (usually
    within 10% of the `replicas` value.

If any of the above look suspicious considering a differing remediation option
pending the investigation into the target Deployment that appears unhealthy.

## Remediation

> [!important]
> Do not use the `helm rollback` command. `helm rollback` will roll the code that is running in an
> environment back to a previous version. We can not be certain that this is safe, because
> post-deployment migrations may already have been run for the previous version. So, we should
> **always** roll forward when Helm is stuck. Deleting the Helm version Secret does not affect the
> code that is running in our cluster, and hence, is a safer way to recover when Helm is stuck.

1. Validate that no deployments or configuration changes are attempting to be
   rolled out
   * Check for any running CI jobs that are targeting this cluster
1. Log into the cluster
   * Ensure all Deployments indicate they are not stuck (as described above)
1. Identify the "failed" release `helm list --namespace gitlab`
   * Replace the appropriate namespace as needed
   * Document the noted Revision Number
1. Find the secret object associated with the failed release and delete it
   * Example: The `gitlab-cny` release with revision `1234` is stuck, we'd run
     the following command: `kubectl delete secret --namespace gitlab-cny
     sh.helm.release.v1.gitlab-cny.v1234`
   * Replace the namespace and target secret as necessary
1. Validate that the `helm status` indicates the deploy is complete
1. Continue remediation pending the situation that brought you here

## Post Remediation

**Note:** Deleting the secret will not impact what is running on the cluster.
Instead this only impacts Helm state.  In this case, we are removing what Helm
thought the cluster should be running and instead Helm will think we're minus 1
revision.  Thus it is important to understand what Helm will show the next time
a configuration change or Auto-Deploy may look like in the eyes of Helm come
around the next attempted Dry Run.  For example:

* If a configuration change was rolled back, that config change will remain on
  the cluster, but the next Dry Run execute by Helm will think that config
  change may need to be rolled out again.
* If an auto-deploy got stuck, the next time a Helm Dry Run executes, it'll
  think that GitLab may need to be upgraded

In all situations, we can observe the actual deployment objects that need to be
questioned for validation.  It is recommended to try to see that Helm is in a
safe place prior to ending calling a situation remediated.  This may mean
rerunning the latest failed CI job.  This will usually detect a "change," but
upon closer inspection, no changes end up deployed.
