# How to take a snapshot of an application running in a StatefulSet

!!! WARNING! this procedure has only ever been tested in staging, not in production! Use it with caution! It was captured here so that we have a written track of what might be useful in the future !!!

Some questions that need to be answered before gaining more confidence:

- Is there any other cleanup concerns we need to be aware of? Such as removing the snapshots afterwards?
- Does this procedure confuse Helm? (for example, does help add some metadata to the StatefulSet objects)

Examples of when this procedure might be useful:

- regular backup and restore of StatefulSet Apps (e.g. Redis or Postgres)
- prepare a rollback procedure for an update to a StatefulSet App (e.g. Prometheus)

## Procedure for taking snapshots of statefulsets

1. Go to GCP console and take snapshot of all volumes
1. Take note of names of volumes in GCP and dump all yamls from k8s to a persistent location (such as a disk)
1. Delete statefulset object, leaving pods in place: `kubectl delete --cascade=orphan sts/<statefulset_name>` src: <https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/kube/k8s-pvc-resize.md>
1. Delete one pod
1. Delete one pvc (which should result in pv in k8s being deleted and volume in GCP being deleted)
1. Create a volume in GCP from a snapshot, the resulting volume should have the same name as the original one
1. Create pv pointing to the new volume, don't create the pod, don't create the pvc
1. Recreate statefulset and let it create the pod and pvc (which should get bound to the existing PV)

Further reading: <https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/preexisting-pd#pv_to_statefulset>
