# Redis on Kubernetes

This documentation covers Redis-specific tools and techniques.

For CPU profiling, packet captures, `pidstat` usage, and other general-purpose observability tools/techniques, see
[Ad hoc observability tools on Kubernetes nodes](../kube/k8s-adhoc-observability.md)

## Redis CLI

Here we cover how to connect to redis using `redis-cli` from either your laptop (via `kubectl`) or the GKE node (via `crictl`).

The `redis` or `sentinel` container includes the `redis-cli` executable, so we can run it in either of those containers.

To authenticate `redis-cli`, within the container we can set the `REDISCLI_AUTH` env var to the contents of the file named by `REDIS_PASSWORD_FILE`.

Here are a few options for doing that.

For any of these, we can pass arbitrary [Redis commands](https://redis.io/commands/) to `redis-cli`, but be mindful of escaping.

From the GKE node where a redis pod is running:

```
# Pick the container id:
$ CONTAINER_ID=$( crictl ps --latest --quiet --name redis )

# Then use any of these options to authenticate redis-cli:

$ crictl exec -it $CONTAINER_ID bash -c 'REDISCLI_AUTH=$( cat $REDIS_PASSWORD_FILE ) redis-cli'

or

$ crictl exec -it $CONTAINER_ID bash
$ export REDISCLI_AUTH=$( cat $REDIS_PASSWORD_FILE )
$ redis-cli

or

$ REDIS_PASSWORD=$( crictl exec $CONTAINER_ID bash -c 'cat $REDIS_PASSWORD_FILE' )
$ crictl exec -it $CONTAINER_ID env REDISCLI_AUTH=$REDIS_PASSWORD redis-cli
```

From your laptop using kubectl:

```
# Pick a Redis pod:

$ kubectl get pods -n redis
$ kubectl get pods -A -l 'app.kubernetes.io/name=redis'

# Then run redis-cli from the redis container of your chosen pod:

$ kubectl exec -it -n redis -c redis $POD_NAME -- bash
$ export REDISCLI_AUTH=$( cat $REDIS_PASSWORD_FILE )
$ redis-cli

or

$ kubectl exec -it -n redis -c redis $POD_NAME -- bash -c 'REDISCLI_AUTH=$( cat $REDIS_PASSWORD_FILE ) redis-cli'
```

Example:

```
$ for POD_NAME in redis-ratelimiting-node-{0..2} ; do echo "Pod: $POD_NAME" ; kubectl exec -n redis -c redis $POD_NAME -- bash -c 'REDISCLI_AUTH=$( cat $REDIS_PASSWORD_FILE ) redis-cli role | head -n1' ; done
Pod: redis-ratelimiting-node-0
slave
Pod: redis-ratelimiting-node-1
slave
Pod: redis-ratelimiting-node-2
slave
```

## Redis RDB dump analysis

An RDB dump is a point-in-time backup of a redis database.
It can be useful for analyzing data properties, such as the count and size distributions of redis keys.

The next section covers how to obtain an RDB dump file from a Redis pod in GKE.

As follow-up once you have the dump file, see these tips on analyzing that dump file:
[Redis key size estimation](redis.md#key-size-estimation)

### Obtain an RDB dump file

The redis container writes its RDB dump file to container path `/data/dump.rdb`.
Container path "/data" is a persistent volume acting as the `REDIS_DATA_DIR`.

The simplest way to download a file from a container is to use `kubectl cp`, but that poses several problems:

* It is painfully slow (< 1 MB/s), untennable large files like RDB dumps.
* It is prone to failing partway into the download, even if the pod and node remain healthy, wasting time and losing the point-in-time.
* It implicitly increases the disk space usage on the redis volume, because the next scheduled dump cannot deallocate the old dump's inode while the file is downloading.
  Under certain conditions, this could fill the volume and cause redis to fail.

We can avoid those risks and inefficiencies.

Instead, we can copy the file out of the container and download it using `gcloud compute scp`.

Quick reference:

```
Find the "redis" container's id:
$ CONTAINER_ID=$( crictl ps --quiet --latest --name redis )

Confirm the dump file exists.
Note: Typically redis periodically overwrites it, but once we start copying it, we get a stable point in time.
$ crictl exec $CONTAINER_ID ls -lh /data/dump.rdb

Find the host path for that container's "/data" volume:
$ DATA_DIR_HOST_PATH=$( crictl inspect $CONTAINER_ID | toolbox jq -r '.status.mounts[] | select(.containerPath == "/data") | .hostPath' 2> /dev/null )

Confirm that the RDB dump file exists and is fresh enough:
$ sudo ls -lh $DATA_DIR_HOST_PATH/dump.rdb

Copy the RDB dump file to your home dir (a path on a large filesystem that is readable without sudo):
$ df -hT ~/
$ sudo cp -pi $DATA_DIR_HOST_PATH/dump.rdb ~/

Download the RDB dump file to your laptop:
$ gcloud compute scp --project $GCP_PROJECT $GKE_HOSTNAME:dump.rdb .
```

Demo:

```
# Review the redis pod and its list of containers.

$ crictl pods --namespace redis
POD ID              CREATED             STATE               NAME                        NAMESPACE           ATTEMPT             RUNTIME
0d196eeed77e2       2 days ago          Ready               redis-ratelimiting-node-0   redis               0                   (default)

$ POD_ID=$( crictl pods --latest --quiet --namespace redis )

$ crictl ps --pod $POD_ID
CONTAINER           IMAGE               CREATED             STATE               NAME                ATTEMPT             POD ID
8cd288f526edf       6847317f2c777       2 days ago          Running             process-exporter    0                   0d196eeed77e2
85bcca4b1e4ab       2600417bb7548       2 days ago          Running             metrics             0                   0d196eeed77e2
bd9d556dd3d41       de6f7fadcaf3d       2 days ago          Running             sentinel            0                   0d196eeed77e2
7c31f1409f146       be0431d8c1328       2 days ago          Running             redis               0                   0d196eeed77e2

# Get the id of the container named "redis" (where the redis-server process runs).

$ CONTAINER_ID=$( crictl ps --quiet --pod $POD_ID --name redis )

# Find the host path corresponding to the volume mounted at container path "/data".

$ DATA_DIR_HOST_PATH=$( crictl inspect $CONTAINER_ID | toolbox jq -r '.status.mounts[] | select(.containerPath == "/data") | .hostPath' 2> /dev/null )

# Confirm the RDB dump file exists.

$ sudo ls -1 $DATA_DIR_HOST_PATH/dump.rdb
/var/lib/kubelet/pods/5f01c0a3-1b86-46c4-81b0-53fab3cff523/volumes/kubernetes.io~gce-pd/pvc-0e3e499b-0840-47f0-a0d5-5e507cd4f9f5/dump.rdb

# Copy the file out of the container to a path you can access without sudo on the host (e.g. your home dir).
# Ensure the filesystem has enough free space.

$ df -hT ~/
$ sudo cp -pi $DATA_DIR_HOST_PATH/dump.rdb ~/

# Download the file to your laptop.

$ gcloud compute scp --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-tboc:dump.rdb /tmp/
```
