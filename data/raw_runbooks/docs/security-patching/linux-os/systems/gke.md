# GKE

## Overview

Container-Optimized OS versions are directly tied to the deployed GKE version. Google [manages](https://cloud.google.com/kubernetes-engine/docs/resources/security-patching) the patching and release of security fixes for these images, and updates are applied as nodes are upgraded to newer GKE versions. All of our clusters have automatic node pool upgrades enabled, so we should monitor to ensure that our Kubernetes major and minor versions are within Google's [support window](https://cloud.google.com/kubernetes-engine/docs/release-schedule#schedule-for-release-channels) and allow for automatic updates within each cluster's release channel. This will ensure that nodes remain up to date with security patches.

It is possible that non-evictable, or critical, workload may be scheduled on a node, preventing it from being replaced and upgraded. In these scenarios, care should be taken to monitor for this and plan to move the Pods to newer instances when safe. And while it should be rare, workloads that are not deployed in a highly available manner (Zoekt, being one example), may incur service disruptions while they are being evicted from nodes.

Google publishes a [JSON mapping](https://www.gstatic.com/gke-image-maps/gke-to-cos.json) of COS version to GKE versions.

Example of what to expect during a security update made by Google to a cluster running 1.28.9

![gke patch update](../img/gke-update.png)

## Skew detection

It's possible that nodes can fall behind on their GKE versions due to previously mentioned constraints around workload eviction. To detect this, the following Prometheus query can be used to see what the latest GKE node version on the cluster is, and see if any nodes are older than that.

[Grafana Explore](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22i9z%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22B%22,%22expr%22:%22count%28kube_node_info%7Benvironment%3D%5C%22gprd%5C%22%7D%29%20by%20%28kubelet_version,%20cluster%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-gprd%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)

## Manually initiated COS upgrades

Vulnerabilities may be discovered that exist in a COS image, where Google's remediation is slower to propagate through the release channels than desired. In these cases, one can refer to the [JSON mapping](https://www.gstatic.com/gke-image-maps/gke-to-cos.json) to determine the GKE version that contains the fix for discovered vulnerabilities, and then initiate cluster upgrades to this version. ***This may require changing the cluster release channel***

## Automation

For day to day operations, no action is generally required from SREs to keep nodes up to date with security patches. Google automatically initiates node pool replacements when new versions are available to address security vulnerabilities within the specified release channel, and defined maintenance windows.

To ensure these updates are consistently available however, it is on the infrastructure teams to ensure that the Kubernetes versions deployed, are still within their support window. Initiating upgrades of the Kubernetes version may not always be automatic.

A tool like [Renovate](https://github.com/renovatebot/renovate) may also be able to be used to help initiate Kubernetes version upgrades via automated MR creation against the [config-mgmt](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt) repository that contains the Terraform used to provision the clusters.
