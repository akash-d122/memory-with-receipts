## Summary

_Note: Before starting an on-call shift, be sure you follow these setup
instructions_

Majority of our Kubernetes configuration is managed using these projects:

* <https://gitlab.com/gitlab-com/gl-infra/argocd/apps>
* <https://gitlab.com/gitlab-com/gl-infra/argocd/config>
* <https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com>

:warning: CI jobs are executed on the ops instance. :warning:

:warning: Deployer makes changes to the cluster config outside of git, but using pipelines in these projects. This means that the state of the cluster is often not reflected in the projects linked above. However, it usually should be possible to trace down the CI job that applied the change. :warning:

They include CI jobs that apply the relevant config to the right cluster. Most of what we do does not require interacting with clusters directly, but instead making changes to code in these projects.

## Kubernetes API Access

Certain diagnostic steps can only be performed by interacting with Kubernetes
directly. For this reason you need to be able to run `kubectl` commands. Remember
to avoid making any changes to the clusters config outside of git!

We use private GKE clusters, with the control plane only accessible from within
the cluster's VPC or the [VPN](https://handbook.gitlab.com/handbook/security/corporate/systems/vpn/).

1. Setup Yubikey SSH keys: <https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/uncategorized/yubikey.md>
1. Setup bastion for clusters: <https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/bastions>
1. Install `gcloud`: <https://cloud.google.com/sdk/docs/install>
1. Install [`gke-gcloud-auth-plugin`](https://cloud.google.com/blog/products/containers-kubernetes/kubectl-auth-changes-in-gke): `gcloud components install gke-gcloud-auth-plugin`.
1. Install `kubectl`:

   * [MacOS](https://kubernetes.io/docs/tasks/tools/install-kubectl-macos/)
   * [Linux](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)

1. Run `gcloud auth login`: The browser will open to choose with google email address to use to allow for oauth.

   💡 *If you see warnings about permissions issues related to `~/.config/gcloud/*` check the permissions of this directory. Simply change it to your user if necessary: `sudo chown -R $(whoami) ~/.config`* 💡

**Option A: VPN**

1. Run `glsh kube setup --no-proxy`: use [`glsh`](../../README.md#running-helper-scripts-from-runbook) to set up the `kubectl` configuration to be able to talk to all clusters without a proxy.
1. Launch NordLayer and [connect to one of the organization gateways](https://handbook.gitlab.com/handbook/security/corporate/systems/vpn/#nordlayer-for-system-administration) (:warning: not to a shared gateway!)
1. Run `glsh kube use-cluster`: this will print all the available clusters.
1. Run `glsh kube use-cluster gstg --no-proxy`: this will connect you to the `gstg` regional cluster.

   Alternatively, you can directly run `kubectx` to select a cluster from an interactive menu.

1. Run `kubectl get nodes`: this will list all the nodes available in the cluster.

**Option B: SOCKS5 proxy via SSH**

1. Run `glsh kube setup`: use [`glsh`](../../README.md#running-helper-scripts-from-runbook) to set up `kubectl` configuration to be able to talk to all clusters via a SOCKS5 proxy.
1. Run `glsh kube use-cluster`: this will print all the available clusters.
1. Run `glsh kube use-cluster gstg`: this will connect you to the `gstg` regional cluster.
1. In a new window run `kubectl get nodes`: this will list all the nodes available in the cluster.

### GUI consoles and metrics

When troubleshooting issues, it can often be helpful to have a graphical
overview of resources within the cluster, and basic metric data.  For more
detailed and expansive metric data, we have a number of [dashboards within
Grafana](https://dashboards.gitlab.net/dashboards/f/kubernetes/kubernetes).
For tunneling mechanism above `glsh kube use-cluster $CLUSTER`, one excellent
option for a local graphical view into the clusters that works with both is the
[Lens IDE](https://k8slens.dev/).  Alternatively, the [GKE
console](https://console.cloud.google.com/kubernetes) provides access to much
of the same information via a web browser, as well.

## Shell access to nodes and pods

### Accessing a node

* [ ] Initiate an SSH connection to one of the production nodes, this requires a fairly recent version of gsuite

```bash
kubectl get pods -o wide  # find the name of the node that you want to access. The `NODE` column shows you the name of the node where each pod is scheduled
gcloud compute --project "gitlab-production" ssh <node name> --tunnel-through-iap
```

This will create an ssh key that is propagated to the GCP project to allow access.  You may receive a message from SIRTBot afterwards.

* [ ] From the node you can list containers, and get shell access to a pod as root.  At this writing our nodepools run a mix of docker and containerd, but eventually we expect them to be all containerd.

When using the code snippets below on docker nodes, change `crictl` to `docker`; they are functionally mostly equivalent for common basic tasks.

To quickly see if a node is running docker without explicitly looking it up, run `docker ps`; any containers listed in the output means it is a docker node, and empty output means containerd

```bash
crictl ps
crictl exec -u root -it <container> /bin/bash
```

* [ ] You shouldn't install anything on the GKE nodes. Instead, use toolbox to troubleshoot problems, for example run strace on a process running in one of the GitLab containers. You can install anything you want in the toolbox container.

```bash
gcloud compute --project "gitlab-production" ssh <node name>
toolbox
```

for more documentation on toolbox see: <https://cloud.google.com/container-optimized-os/docs/how-to/toolbox>

For more troubleshooting tips see also: [attach to a running container](./k8s-operations.md#attaching-to-a-running-container)

### Accessing a pod

* [ ] Initiate an interactive shell session in one of the pods. Bear in mind, that many containers do not include a shell which means you won't be able to access them in this way.

```bash
kubectl exec -it <pod_name> -- sh
```

## Running kubernetes config locally

There are certain scenarios in which you might want to evaluate our kubernetes config locally. One such scenario is during an incident, when the CI jobs are unable to run. Another is during development, when you want to test the config against a local cluster such as minikube or k3d.

In order to be able to run config locally, you need to install tools from the projects with kubernetes config linked above.

### Install tools

* [ ] Checkout repos from all projects
* [ ] Install tools from them. They contain a `.tool-versions` file which should be used with [`mise`](https://mise.jdx.dev/), for example: `cd k8s-workloads/gitlab-com; mise install`

### Workstation setup for k-ctl

* [ ] Get the credentials for the pre-prod cluster:

```bash
gcloud container clusters get-credentials pre-gitlab-gke --region us-east1 --project gitlab-pre
```

* [ ] Setup local environment for `k-ctl`

These steps walk through running `k-ctl` against the preprod cluster but can also be used to connect to any of the staging or production clusters using sshuttle above.
It is probably very unlikely you will need to make a configuration change to the clusters outside of CI, follow these instructions for the rare case this is necessary.
`k-ctl` is a shell wrapper used by the [k8s-workloads/gitlab-com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com) over `helmfile`.

```bash
git clone git@gitlab.com:gitlab-com/gl-infra/k8s-workloads/gitlab-com
cd gitlab-com
export CLUSTER=pre-gitlab-gke
export REGION=us-east1
./bin/k-ctl -e pre list
```

You should see a successful output of the helm objects as well as custom Kubernetes objects managed by the `gitlab-com` repository.

Note that if you've renamed your kube contexts to something less unwieldy, you
can make the wrapper use your current context:

```bash
kubectl config use-context pre
FORCE_KUBE_CONTEXT=1 ./bin/k-ctl -e pre list
```

* [ ] Make a change to the preprod configuration and execute a dry-run

```bash
$ vi releases/gitlab/values/pre.yaml.gotmpl
# Make a change
./bin/k-ctl -e pre -D upgrade
```

## Getting or setting HAProxy state for the zonal clusters

It's possible to drain and stop connections to an entire zonal cluster.
This should be only done in extreme circumstances where you want to stop traffic to an entire availability zone.

* [ ] Get the server state for the production `us-east1-b` zone

_Use the `bin/get-server-state` script in [chef-repo](https://ops.gitlab.net/gitlab-cookbooks/chef-repo/)_

```bash
./bin/get-server-state gprd gke-us-east1-b
```

`./bin/set-server-state` is used to set the state, just like any other server in an HAProxy backend

## Troubleshooting

### Connection to the server refused

If `kubectl get nodes` returns an error like "The connection to the server xx.xx.xxx.xx was refused - did you specify the right host or port?", this probably means SSH access via bastion was not set up properly. Refer to the [bastion setup documentation](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/bastions) to set up your bastion SSH access. You can use your yubikey to set up your SSH keys by following [documentation here](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/uncategorized/yubikey.md).
