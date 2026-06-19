# Isolating a pod

The following is a guide on how to isolate pods for troubleshooting, profiling, inspection, etc.
Our current application configuration components:

* <https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com>
* <https://gitlab.com/gitlab-com/gl-infra/argocd/apps>

## Preamble

Each pod has labels associated with it. Depending if we need the pod to coninue getting requests or not different label(s) need to be removed.

The deployment itself has defined labels in the `spec` => `selector` => `matchLabels` fields. There are labels for the service as well.

If we take a random pod and remove a label that is defined in the deployment Kubernetes will need to schedule a new one to satisfy the requirement.
When this happens we will have n+1 number of pods, as we've isolated one by removing the label. Deployments will not impact this pod as it will not be considered part of the deployment.

This is useful when we need to do a rollout of a fix _while_ having a pod from the previous version that we can use for testing purposes.

## How to actually do it

If we check a deployment with `kubectl describe deploy --namespace=gitlab NAME` where NAME is the name of the deployment we will see the labels used for pods.
The next step is to find the pod we want to isolate by editing it's pod spec by removing the label associated with the selector:

```shell
kubectl edit pod --namespace=gitlab POD_NAME_HERE
```

```yaml
labels:
  example: true
  component: app
```

By commenting or removing any label, for example the "example" label we isolate the pod. The pod _may_ still receive requests depending on the labels that are defined in the service.

To check if we've successfuly isolated the pod we can run `kubectl get pods --namespace=gitlab --watch` to see if a new pod is scheduled.

## Side-effects

When isolating the pod we may need to ensure that the pod is removed/deleted after our troubleshooting as it's a rogue pod.
