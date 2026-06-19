# NATS Operations

For general operations it is recommended to rely on `helm` mechanisms to control and configure the NATS release. It is controlled via environment specific configurations like [here](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/nats/env/analytics-eventsdot-stg).

Cluster replicas be increased by changing:

```diff
--- a/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
+++ b/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
@@ -11,7 +11,7 @@ config:
     enabled: true
     name: analytics-eventsdot-stg
     port: 6222
-    replicas: 3
+    replicas: 5

   jetstream:
     enabled: true

```

However increasing the NATS Jetstream storage is not quite as simple as increasing the `size` in helm values. This is because how Kubernetes doesn't allow StatefulSets spec to be modified expect few selected fields.

```diff
--- a/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
+++ b/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
@@ -22,7 +22,7 @@ config:

       pvc:
         enabled: true
-        size: 100Gi
+        size: 200Gi
```

So we need to following additional steps to actually sync the above helm state with the cluster.

1. List the PVCs first

    ```shell
    $ kubectl get pvc -l app.kubernetes.io/name=nats -n <namespace>
    ````

1. Patch each pvc individually with the increase to its storage size

    ```shell
    # This assumes 3 PVCs as per the above output, should be adjusted for actual count
    for i in 0 1 2; do
      kubectl patch pvc nats-js-nats-$i -n nats \
        --type merge -p '{"spec":{"resources":{"requests":{"storage":"3Ti"}}}}'
    done
    ```

1. Force a deletion of `nats` StatefulSet **without deleting the actual pods**

    ```shell
    kubectl delete statefulset nats -n nats --cascade=orphan
    ```

1. Sync helm changes with the cluster which will create the StatefulSet with update storage

[NATS cli](https://github.com/nats-io/natscli) is also available on the deployed environments via the `nats-box` deployment. During troubleshooting or incidents operational tasks like restart, configuration changes can be done in the `nats-box` container.

NATS administration [doc](https://docs.nats.io/running-a-nats-service/nats_admin) provide good reference on additional operational tasks.
