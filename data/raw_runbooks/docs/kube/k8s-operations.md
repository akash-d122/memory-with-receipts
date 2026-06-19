# GitLab

<https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com>

## Setup for the oncall

**!Important!** Before you do anything in this doc please follow the [setup instructions for the oncall](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/kube/k8s-oncall-setup.md).

## Application Upgrading

- Setting the version of the Helm Chart utilized by .com can be accomplished by following the instructions for [Setting Chart Version](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/tree/master#setting-chart-version)
- Most services are handled via Auto-Deploy.  Some are not, reference [DEPLOYMENT.md](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/DEPLOYMENT.md#auto-deploy)

## Creating a new node pool

Creating a new node pool will be necessary if we need to change the instance sizes of our nodes or any setting that requires nodes to be stopped.
It is possible to create a new pool without any service interruption by migrating workloads.
The following outlines the procedure, note that when doing this in production you should create a change issue, see <https://gitlab.com/gitlab-com/gl-infra/production/issues/1192> as an example.

**Note**: When creating a new node pool to replace an existing node pool, be sure to use the same [`type`](https://gitlab.com/gitlab-com/gitlab-com-infrastructure/-/blob/c33ca88c65a7be73f946c750a6eb988b2a982b12/environments/gprd/gke-regional.tf#L172) for pod scheduling.

```
OLD_NODE_POOL=<name of old pool>
NEW_NODE_POOL=<name of new pool>
```

- Add the new node pool to Terraform by creating a new entry in the relevant TF environment, for example for staging you'd add an entry [here](https://ops.gitlab.net/gitlab-com/gitlab-com-infrastructure/-/blob/master/environments/gstg/gke-zonal.tf#L47).
- Apply the change and confirm the new node pool is created
- Cordon the existing node pool

```bash
for node in $(kubectl get nodes -l cloud.google.com/gke-nodepool=$OLD_NODE_POOL -o=name); do \
  kubectl cordon "$node"; \
  read -p "Node $node cordoned, enter to continue ..."; \
done

```

- Evict pods from the old node pool

```bash
for node in $(kubectl get nodes -l cloud.google.com/gke-nodepool=$OLD_NODE_POOL -o=name); do \
  kubectl drain --force --ignore-daemonsets --delete-local-data --grace-period=10 "$node"; \
  read -p "Node $node drained, enter to continue ..."; \
done
```

- Delete the old node pool manually (in GCP console or on the command line)
- Remove all node pools from the Terraform state

```bash
tf state rm module.gitlab-gke.google_container_node_pool.node_pool[0]
tf state rm module.gitlab-gke.google_container_node_pool.node_pool[1]
```

- Import the new node pool into Terraform

```
tf import module.gitlab-gke.google_container_node_pool.node_pool[0] gitlab-production/us-east1/gprd-gitlab-gke/$NEW_NODE_POOL
```

- Update Terraform so that the new node pool is the only one in the list

## Manual Scaling a Deployment

In times of emergency, whether it be a security issue, identified abuse, and/or an incident where there's great pressure in our infrastructure, it may be necessary to manually set the scale of a Deployment.
When a Deployment is setup with a Horizontal Pod Autoscaler (HPA), and we need to manually scale, be aware that the HPA will fail to autoscale if we scale down to 0 Pods.
Also keep in mind that an HPA will process metrics on a regular cadence, if you scale w/i the window of the HPA configuration, the manual override will quickly be taken over by the HPA.

To scale a deployment, run the following example command:

```
kubectl scale <DEPLOYMENT_NAME> --replicas=<X>
```

Example, scale Deployment `gitlab-sidekiq-memory-bound-v1` to 0 Pods:

```
kubectl scale deployments/gitlab-sidekiq-memory-bound-v1 --replicas=0
```

The `DEPLOYMENT_NAME` represents the Deployment associated and managing the Pods
that are running. `X` represents the desired number of Pods you wish to run.

After an event is over, the HPA will need at least 1 Pod running in order to
perform its task of autoscaling the Deployment. For this, we can rerun a
similar command above, using the below as an example:

```
kubectl scale deployments/gitlab-sidekiq-memory-bound-v1 --replicas=1
```

Refer to existing Kubernetes documentation for reference and further details:

- <https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/>
- <https://github.com/kubernetes/community/blob/master/contributors/design-proposals/autoscaling/horizontal-pod-autoscaler.md>

## Rotating/Restarting a Deployment

In some cases there might be a need to rotate all pods for a workload (e.g. feature flags that require an app restart).
This can be triggered by using `kubectl rollout restart`.

Example:

```sh
kubectl -n gitlab rollout restart deployment/gitlab-gitlab-shell
```

Status of the deployment rotation can be checked with:

```sh
kubectl rollout status -n gitlab deployment/gitlab-gitlab-shell
```

## Deployment lifecycle

Kubernetes keeps replicasets objects for a limited number of revisions of deployments. Kubernetes events are not created for a replicaset creation/deletion. Only for pods creation/deletion within a replicaset. Similarly, there are no events created for changes to Deployments.

The most complete source of information about changes in kubernetes clusters is the audit log that in GKE is enabled by default. To access audit log, go to Logs Explorer (Stackdriver) in the relevant project in the GCP console.

### diff between deployment versions

An example of how you can get a diff between different deployment versions using rollout history (revisions have to exist in the cluster)

```
kubectl -n gitlab rollout history deployment/gitlab-gitlab-shell  # get all deployment revisions
kubectl -n gitlab rollout history deployment/gitlab-gitlab-shell --revision 22 > ~/deployment_rev22  # get deployment yaml at rev 22
kubectl -n gitlab rollout history deployment/gitlab-gitlab-shell --revision 21 > ~/deployment_rev21  # get deployment yaml at rev 21
```

You can also find the diff in the body of the patch request sent to the apiserver. These are logged in the audit logs. You can find these events with this search:

```
protoPayload.methodName="io.k8s.apps.v1.deployments.patch"
```

### timestamp of a change to Deployment

Check our deployment pipelines on the ops instance, in the projects holding kubernetes config.

If the ReplicaSet objects still exist, you can look at their creation timestamp in their definition.

Audit log also contains a lot of useful information. For example, deployment patching events (e.g. on image update):

```
protoPayload.methodName="io.k8s.apps.v1.deployments.patch"
```

Replicaset creation (e.g. on image update):

```
protoPayload.methodName="io.k8s.apps.v1.replicasets.create"
```

## Attaching to a running container

Keep in mind that the below steps are operating on a production node and
production container which may be servicing customer traffic. Some
troubleshooting may incur performance penalties or expose you and tooling to
Red classified data. Consider removing the Pod after your work is complete.

We just need the following information:

- target Pod
- container we want to exploit
- node it's running on

Firstly, figure out what node/zone a Pod is running:

```
kubectl get pods -n gitlab -o wide # get the node name
pod_name=<POD_NAME>
node_name=<NODE_NAME>
zone=$(gcloud compute instances list --filter name=$node_name --format="value(zone)") # get the zone
```

We now need to figure out the container ID:

```
kubectl get pod $pod_name -o json | jq .status.containerStatuses
```

In the output, if there's multiple containers, find the one you want, followed
by that objects' `containerID`. This is a very long ID, and we may need it
later. Note that down, we'll need it later.

SSH into the node:

```
gcloud compute ssh $node_name --zone=$zone --tunnel-through-iap
```

Get the container ID:

```
crictl ps | grep 'websockets-57dbbcdcbd-crv2p'
```

If the container contains all the tools you need, you can simply exec into it:

```
crictl exec -it 7aa3c4ad2775c /bin/bash
```

Where `7aa3c4ad2775c` is the container id that you have already found. If it doesn't have `/bin/bash`, try `/bin/sh` or just `exec`ing `ls` to find what binaries are available.

At this point we can install some tooling necessary and interrogate the best we can. Remember that the container could be shutdown at any time by Kubernetes, and any changes are very transient.

If you need higher permissions or more tooling in the container, examples include needing a root shell or perhaps a tool you need does not exist on the image, you can attach another container to the same network/pid namespaces when running.

```sh
runc --root /run/containerd/runc/k8s.io/ \
  exec \
  -t \
  -u 0 \
  $container_id \
  /bin/bash
```

Or use whatever shell you know is readily available. Note you need the entire
container ID that you had found earlier, `runc` will toss you an error that the
container does not exist if a shortened ID is utilized. Note we are using `runc`
here, as `crictl` does not provide us this capability. `runc` is the underlying
runtime, `containerd` is how Kubernetes interfaces with it.

### Using Toolbox

GKE nodes by design have a very limited subset of tools. If you need to conduct troubleshooting directly on the host, consider using toolbox. Toolbox is a container that is started with the host's root filesystem mounted under `/media/root/`.
The toolbox's file system is available on the host at `/var/lib/toolbox/`.

You can specify which container image you want to use, for example you can use `coreos/toolbox` or build and publish your own image.
There can only be one toolbox running on a host at any given time.

For more details see: <https://cloud.google.com/container-optimized-os/docs/how-to/toolbox>

### Debugging containers in pods

Quite often you'll find yourself working with containers created from very small images that are stripped of any tooling. Installation of tools inside of those containers might be impossible or not recommended. Changing the definition of the pod (to add a debug container) will result in recreation of the pod and likely rescheduling of the pod on a different node.

One way to workaround it is to investigate the container from the host. Below are a few ideas to get you started.

#### Run a command with the pod's network namespace

1. Find the PID of any process running inside the pod, you can use the pause process for that (network namespace is shared by all processes/containers in a pod). There are many, many ways to get the PID, here are a few ideas:
   - `containerd` Get PID of a process running in a container:
     1. List containers and get container ID: `crictl ps -a`
     1. Get pid of a process in a container with a given ID: `crictl inspect <containerID>` search for `info.pid` field
1. Run a command with the network namespace
   - Entire toolbox started with the given namespace:
     - `toolbox --network-namespace-path=/proc/<container_pid>/ns/net`
   - Alternatively, you can use nsenter on the GKE host (note: it might not be available, toolbox is a safer approach):
     - `nsenter -target <PID> -mount -uts -ipc -net -pid`

#### Attach PVC

An existing volume can be attached to toolbox for debugging using `--bind=` or `--bind-ro=` (read only).

- `toolbox --bind=/var/lib/kubelet/pods/<containerID>/volume-subpaths/<pvc_id>/...`

#### Add an ephemeral debug container (Kubernetes >= 1.23)

<https://kubernetes.io/docs/tasks/debug-application-cluster/debug-running-pod/#ephemeral-container>

This adds a new container inside the pod sharing the same process namespace.

```
kubectl debug -it mypod --image=busybox --target=mypod
```

#### Share process namespace between containers in a pod

<https://kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/>

## Auto-scaling, Eviction and Quota

### Nodes

- Node auto-scaling: <https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler>

Node auto-scaling is part of GKE's cluster auto-scaler, new nodes will be added
to the cluster if there is not enough capacity to run pods.

The maximum node count is set as part of the cluster configuration for the
[node pool in Terraform](https://gitlab.com/gitlab-com/gitlab-com-infrastructure/blob/7e307d0886f0725be88f2aa5fe7725711f1b1831/environments/gprd/main.tf#L1797)

### Pods

- Pod auto-scaling: <https://cloud.google.com/kubernetes-engine/docs/how-to/scaling-apps>

Pods are configured to scale by CPU utilization, targeted at `75%`

Example:

```
kubectl get hpa -n gitlab
NAME              REFERENCE                    TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
gitlab-registry   Deployment/gitlab-registry   47%/75%   2         100       21         11d
```

It is possible to scale pods based on custom metric but this is currently not used in the cluster.

### Quota

There is a [dashboard for monitoring the workload quota for production](https://dashboards.gitlab.net/d/kubernetes-resources-workload/kubernetes-compute-resources-workload?orgId=1&var-datasource=Global&var-cluster=gprd-gitlab-gke&var-namespace=gitlab&var-workload=gitlab-registry&var-type=deployment) that shows the memory quota.

The memory threshold is configures in the [kubernetes config for Registry](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/blob/4b7ba9609f634400e500b3ac54aa51240ff85b27/gprd.yaml#L6)

If a large number of pods are being evicted it's possible that increasing the
requests will help as it will ask Kubernetes to provision new nodes if capacity
is limited.

Kubernetes Resource Management: <https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/>

## Profiling in kubernetes

### Get ContainerID and node name

```bash
kubectl -n pubsubbeat get po pubsubbeat-pubsub-sidekiq-inf-gstg-669679fcbd-hhb2m -o json | jq .status.containerStatuses # All containers returned, save ID of the one you are interested in
NODE_NAME=$(kubectl -n pubsubbeat get po pubsubbeat-pubsub-sidekiq-inf-gstg-669679fcbd-hhb2m -o json | jq -r .spec.nodeName) # Get node name
ZONE=$(gcloud compute instances list --filter name=$node_name --format="value(zone)") # get the zone
gcloud compute ssh --zone $ZONE $NODE_NAME --project "gitlab-production"  # ssh to the GKE node
```

### Prepare toolbox

```bash
toolbox apt install -y jq file
```

### Check for presence of symbols

```bash
$ CONTAINER_ID=3e97fd097b8eb9c2d71fdf9641dfa1cba189f4b110a57c939de59292912b5afd  # Set the value taken from previous `kubectl get po` command.
$ crictl exec -it $CONTAINER_ID top -c  # list processes in the container and find the path of the binary
UID                 PID                 PPID                C                   STIME               TTY                 TIME                CMD
root                2932207             2932188             0                   14:28               ?                   00:00:00            /bin/sh -c /bin/pubsubbeat -c /etc/configmap/pubsubbeat.yml -e 2>&1 | /usr/bin/rotatelogs -e /volumes/emptydir/pubsubbeat.log 50M
root                2932237             2932207             99                  14:28               ?                   03:05:29            /bin/pubsubbeat -c /etc/configmap/pubsubbeat.yml -e
root                2932238             2932207             0                   14:28               ?                   00:00:00            /usr/bin/rotatelogs -e /volumes/emptydir/pubsubbeat.log 50M
$ CONTAINER_ROOTFS="$(sudo cat /run/containerd/runc/k8s.io/$CONTAINER_ID/state.json | toolbox -q jq -r .config.rootfs)"  # find the path to the root fs of the container
$ toolbox -q file "/media/root$CONTAINER_ROOTFS/bin/pubsubbeat"  # check if the binary contains symbols, the last column should say: "not stripped"
/media/root/run/containerd/io.containerd.runtime.v2.task/k8s.io/6c2efcce756520ee87d44fcef240e784bc1fb19c67ea1b27a5a6e198620f0651/rootfs/bin/pubsubbeat: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, Go BuildID=mocZaRlBkbCciCWvbae0/jd2tWQJoTiGknHio9Lgw/8XHiDaWStpC9onSk_TwM/82Iaw_TMpLExCoau_B1N, not stripped
```

### Collect `perf record` data

#### on the entire node

```bash
sudo perf record -a -g -e cpu-cycles --freq 99 -- sleep 60
```

#### on a single container

If the binary running in the container doesn't contain symbols, the data you collect will include empty function names (will not provide a lot of value).

```bash
CONTAINER_ID=$(crictl ps -q --name pubsubbeat_pubsubbeat-pubsub-rails)  # Find the ContainerID of the container you want to profile
CONTAINER_CGROUP=$(crictl inspect $CONTAINER_ID | toolbox -q jq -r .info.runtimeSpec.linux.cgroupsPath)  # Find the cgroup of the container
sudo perf record -a -g -e cpu-cycles --freq 99 --cgroup $CONTAINER_CGROUP -- sleep 60
```

### Extract stacks from `perf record` data with `perf script`

```bash
sudo perf script --header | gzip > stacks.$(hostname).$(date +'%Y-%m-%d_%H%M%S_%Z').gz
```

### Download `perf script` output

So that we avoid installing additional tooling on the GKE node.

On your localhost:

```bash
gcloud compute scp --zone "us-east1-c" "gke-gprd-gitlab-gke-sidekiq-urgent-ot-9be5be8a-o05q:stacks.gke-gprd-gitlab-gke-sidekiq-urgent-ot-9be5be8a-o05q.2021-03-05_173617.gz" --project "gitlab-production" .
gunzip stacks.gke-gprd-gitlab-gke-sidekiq-urgent-ot-9be5be8a-o05q.2021-03-05_173617.gz
```

### Visualize using Flamescope

```bash
docker run -d --rm -v $(pwd):/profiles:ro -p 5000:5000 igorwgitlab/flamescope  # open your browser and go to http://127.0.0.1:5000/
```

### Visualize using Flamegraph

```bash
cat stacks.gke-gprd-gitlab-gke-sidekiq-urgent-ot-9be5be8a-o05q.2021-03-05_173617 | stackcollapse-perf.pl --kernel | flamegraph.pl > flamegraph.$(hostname).$(date '+%Y%m%d_%H%M%S_%Z').svg
```

## Bringing a cluster down for Maintenance

The following is a psuedo procedure that must be completed via a Change Request.
The end result after following this procedure is that a single zonal cluster
will no longer be accepting any user traffic and thus should be safe to do
whatever maintenance necessary.  This procedure is written in a way that
prevents any maintenance from negatively interfering with Auto-Deployment and
configuration change spawned from the `k8s-workloads/gitlab-com` repository.

:warning: This procedure is targeted for our zonal clusters.  We do **NOT** have
a similar procedure for the regional cluster where Sidekiq currently runs.
:warning:

1. Identify the target cluster to be turned down
1. Identify when deployments/configuration changes may occur on the target
   cluster
    - This is to ensure that we work with Release Management to prevent blocking
      deployments as well as catching a cluster back up to the same running
      version of the components after maintenance is completed if necessary.
    - This is to ensure that we work with Infrastructure team members to ensure
      that configuration changes are propagated as desired, and later we catch
      the cluster up if changes were made while the cluster was offline.
1. Gather all HAProxy backend names associated with the cluster
    - We lack consistency in the naming of the backends in HAProxy, thus let's
      document the precise commands required to remove traffic to the cluster.
1. Set environment variable to skip deployments/configurations to the target
   cluster.  Refer to: [`k8s-workloads/gitlab-com/TROUBLESHOOTING.md#skipping-cluster-deployments`](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/TROUBLESHOOTING.md#skipping-cluster-deployments)
1. Remove traffic going to canary from the same zone the HAProxy nodes are
   located in.
    - If this is missed, we risk overloading Canary with traffic on a cluster
      that may not be capable of handling the load.
    - This can be achieved by something similar to: `./bin/set-server-state -z b
      -s 60 gstg maint gke-cny-ssh`
    - The above command will ask all HAProxies located in zone b to set their
      state to `MAINT`, waiting 60 seconds between each HAProxy node to be
      modified.
1. Remove traffic from going to this cluster
    - This can be achieved by something similar to `./bin/set-server-state -z b
      -s 60 gstg maint shell-gke-us-east1-b`
    - The above command will ask all HAProxies located in zone b to set their
      state to `MAINT`, waiting 60 seconds between each HAProxy node to be
      modified.
    - We wait 60 seconds in this example as a way to avoid overloading the
      clusters that remain from becoming overloaded or being unable to scale up
      quickly enough as the load shifts.
1. Validate via metrics that the cluster is receiving the least amount of
   traffic possible
    - Normally the RPS value for a given workload on a target cluster SHOULD be
      0, or the metric will disappear.  For most workloads we exclude
      healthchecks and metrics gathering from displaying as part of our
      dashboards.

## Cluster upgrades

Cluster upgrade operations can be viewed using `gcloud`:

```sh
gcloud --project XXXX container operations list
```

We have a handy list of k8s clusters with their Google project in `../../kubernetes/clusters.json`
so if you want to view the container operations for all k8s clusters in all projects, you can
do the following:

```sh
for project in $(jq -r '.[] | .project' < ../../kubernetes/clusters.json | sort | uniq)
do
  echo "### ${project}"
  gcloud --project $project container operations list
  echo
done
```

You can also view container operations in Google Cloud's operations suite (formerly Stackdriver):

- [Production](https://console.cloud.google.com/logs/query;lfeCustomFields=;query=protoPayload.methodName%3D%22google.container.internal.ClusterManagerInternal.UpdateClusterInternal%22;summaryFields=resource%252Flabels%252Fcluster_name,protoPayload%252Fmetadata%252FoperationType,resource%252Ftype,operation%252Fid:false:32:beginning;timeRange=P7D?project=gitlab-production)
- [Staging](https://console.cloud.google.com/logs/query;lfeCustomFields=;query=protoPayload.methodName%3D%22google.container.internal.ClusterManagerInternal.UpdateClusterInternal%22;summaryFields=resource%252Flabels%252Fcluster_name,protoPayload%252Fmetadata%252FoperationType,resource%252Ftype,operation%252Fid:false:32:beginning;timeRange=P7D?project=gitlab-staging-1)
- [Ops](https://console.cloud.google.com/logs/query;lfeCustomFields=;query=protoPayload.methodName%3D%22google.container.internal.ClusterManagerInternal.UpdateClusterInternal%22;summaryFields=resource%252Flabels%252Fcluster_name,protoPayload%252Fmetadata%252FoperationType,resource%252Ftype,operation%252Fid:false:32:beginning;timeRange=P7D?project=gitlab-ops)
