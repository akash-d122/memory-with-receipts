# Network Info

## Ephemeral runner VMs networking

For high capacity shards (like `shared`) we create dedicated projects for ephemeral VMs.

All these projects have the same networking structure:

| Network Name        | Subnet Name          | CIDR            | Purpose                       |
| ------------------- | -------------------- | --------------- | ----------------------------- |
| `ephemeral-runners` | `ephemeral-runners`  | **UNIQUE CIDR** | Runner manager machines       |
| `runners-gke`       | `runners-gke`        | `10.9.4.0/24`   | Primary; GKE nodes range      |
| `runners-gke`       | `runners-gke`        | `10.8.0.0/16`   | Secondary; GKE pods range     |
| `runners-gke`       | `runners-gke`        | `10.9.0.0/22`   | secondary; GKE services range |

Please read [GCP documentation about `VPC-native
clusters`](https://cloud.google.com/kubernetes-engine/docs/concepts/alias-ips) to understand how the different
ranges of the subnet are being used by GKE.

### VPC Implementation for CI SaaS Hosted Runners

The primary goal is to address scalability challenges due to the limitations of VPC peering and to improve performance, security, and manageability by implementing a shared VPC architecture. This new architecture enables greater flexibility and scalability for ephemeral projects, each linked to a corresponding shard within GCP.

## VPC Architecture

### Previous Architecture

Previously, the CI SaaS infrastructure employed individual VPC peering per project. Each project was paired directly with the central network through unique VPC peering links, which resulted in a highly complex and difficult-to-manage architecture. This approach also led to quickly reaching the VPC peering limit of 70 connections in GCP, which constrained our ability to scale and required re-evaluation of our networking strategy.

![vpc-before](/uploads/065382a656c6f7160d3f262f84e31abf/vpc-before.png)

### New Architecture

The new architecture transitions from individual VPC peerings to a Shared VPC model. This Shared VPC is managed within a central 'gitlab-ci' hub project, with each shard configured as a service project.

The isolation between the shared VPC networks is a logical one, occuring on the application-level, where each runner-manager is configured to use its own isolated network.

By using a Shared VPC, multiple projects can securely communicate through a common network structure, reducing the need for direct VPC peerings and thereby addressing the peering limits.

![vpc-after](/uploads/daa0eb2cec9f1ccc0d2522966dab6167/vpc-after.png)

The architecture provides:

* **Scalability:** Allowing for additional shards without reaching peering limits.
* **Isolation:** Maintaining network security and separation between different shards.
* **Improved Management:** Centralizing control through a single shared VPC with consistent firewall rules and policies.

### Expected Benefits

The new VPC structure provides the following performance and scalability benefits:

* **Improved Scalability:** The Shared VPC approach bypasses the previous 70-peer limit, enabling the CI infrastructure to scale without hitting GCP's peering constraints.
* **Enhanced Isolation and Security:** With each shard operating within its own VPC network, network policies and firewall rules provide stronger isolation, reducing potential security risks.

#### Network peering theory and issues

As peering automatically adds routes, it may introduce a conflict if the network "in the middle" have two different
subnetworks with overlapping CIDR peered. Let's consider few simple examples.

##### Peering conflicting networks directly

```mermaid
graph LR
  classDef subnetwork          color:#fff,fill:#555,stroke:#000,stroke-dasharray: 5 5;
  classDef subnetwork_conflict color:#fff,fill:#555,stroke:#a00,stroke-width:2px,stroke-dasharray: 5 5;
  classDef vpc                 color:#fff,fill:#555,stroke:#000,stroke-width:2px;

  subgraph Network A
    subnetwork_A_1("10.0.1.0/24"):::subnetwork -->|part of| network_A["Network A"]:::vpc
    subnetwork_A_2("10.0.0.0/24"):::subnetwork_conflict -->|part of| network_A
  end

  subgraph Network B
    subnetwork_B_2("10.0.0.0/24"):::subnetwork_conflict -->|part of| network_B["Network B"]:::vpc
    subnetwork_B_1("10.0.2.0/24"):::subnetwork -->|part of| network_B
  end

  network_B ===|peering| network_A

  subnetwork_A_2 -.-|direct conflict| subnetwork_B_2

  linkStyle 5 stroke:#a00,stroke-width:2px,stroke-dasharray: 5 5;
```

In this example we have two networks: `Network A` and `Network B`. Both have two subnetworks defined. One of the
subnetworks in each of the networks is unique (`10.0.1.0/24` in `Network A` and `10.0.2.0/24` in `Network B`).
Both networks contain also a second subnetwork, which have exactly the same CIDR: `10.0.0.0/24`.

When trying to peer these two networks directly, we will get a routing conflict, as it will be impossible to
define where to route traffic to `10.0.0.0/24`. When defining this in GCP (which requires peering definition
to be specified from both sides), first side of peering will be saved. It will be however not activated yet
and GCP will fail and reject to create the second side of the peering.

**Conclusion:** Networks peered directly can't have conflicting CIDRs.

##### Peering conflicting networks with one hop between them

```mermaid
graph LR
  classDef subnetwork          color:#fff,fill:#555,stroke:#000,stroke-dasharray: 5 5;
  classDef subnetwork_conflict color:#fff,fill:#555,stroke:#a00,stroke-width:2px,stroke-dasharray: 5 5;
  classDef vpc                 color:#fff,fill:#555,stroke:#000,stroke-width:2px;

  subgraph Network A
    subnetwork_A_1("10.0.1.0/24"):::subnetwork -->|part of| network_A["Network A"]:::vpc
    subnetwork_A_2("10.0.0.0/24"):::subnetwork_conflict -->|part of| network_A
  end

  subgraph Network B
    subnetwork_B_2("10.0.0.0/24"):::subnetwork_conflict -->|part of| network_B["Network B"]:::vpc
    subnetwork_B_1("10.0.2.0/24"):::subnetwork -->|part of| network_B
  end

  subgraph Network C
    subnetwork_C_1("10.0.3.0/24"):::subnetwork -->|part of| network_C["Network C"]:::vpc
  end

  network_B ===|peering| network_C
  network_C ===|peering| network_A

  subnetwork_A_2 -.-|conflict in Network C| subnetwork_B_2

  linkStyle 7 stroke:#a00,stroke-width:2px,stroke-dasharray: 5 5;
```

Here we extend the previous example with a new network: `Network C`. It has only one subnetwork with unique CIDR:
`10.0.3.0/24`. Instead of peering `Network A` and `Network B` directly, we try to peer them through `Network C`.

For `Network A` there is no problem - it knows only one `10.0.0.0/24` subnetwork - its own. The same goes for
`Network B`.

However, when we will try to connect them both to `Network C`, it will report a conflict as it gets routing to
`10.0.0.0/24` CIDR from two different peers. When trying to apply this in GCP, one peering will be created
successfully. The second one will fail just like in the case of peering conflicting networks directly.

**Conclusion:** Two networks peered through third common network also can't have conflicting CIDRs.

##### Peering conflicting networks with more than one hop between them

```mermaid
graph LR
  classDef subnetwork color:#fff,fill:#555,stroke:#000,stroke-dasharray: 5 5;
  classDef vpc        color:#fff,fill:#555,stroke:#000,stroke-width:2px;

  subgraph Network A
    subnetwork_A_1("10.0.1.0/24"):::subnetwork -->|part of| network_A["Network A"]:::vpc
    subnetwork_A_2("10.0.0.0/24"):::subnetwork -->|part of| network_A
  end

  subgraph Network B
    subnetwork_B_2("10.0.0.0/24"):::subnetwork -->|part of| network_B["Network B"]:::vpc
    subnetwork_B_1("10.0.2.0/24"):::subnetwork -->|part of| network_B
  end

  subgraph Network C
    subnetwork_C_1("10.0.3.0/24"):::subnetwork -->|part of| network_C["Network C"]:::vpc
  end

  subgraph Network D
    subnetwork_D_1("10.0.4.0/24"):::subnetwork -->|part of| network_D["Network D"]:::vpc
  end

  network_B ===|peering| network_D
  network_C ===|peering| network_A
  network_D ===|peering| network_C
```

In this example we add fourth network: `Network D`. It has only one subnetwork with unique CIDR: `10.0.4.0/24`.
We also extend the peering chain, injecting `Network D` in the middle.

With this layout, we finally have no conflicts. `Network A` connected with `Network C` doesn't have any directly
overlapping subnetworks. As `Network C` is connected now with `Network D` it doesn't create conflict for `Network C`
as it was in the previous example.

Then we have `Network D`, which is connected with `Network B` and again without any direct overlapping.

The two only subnetworks that have conflicting CIDRs are now separated with two hops between them. As automatic
routing is being added only for directly connected networks, we have no place where two different routes for
`10.0.0.0/24` would show up.

**Conclusion:** If you need to define conflicting CIDRs, ensure that you have at least two hops when peering the VPC
networks. **Or in other words**: If you have more than two hops when peering VPC networks, you don't need to worry
about CIDR conflicts between the edge networks.

#### Networking layout design

Let's consider this example layout:

```mermaid
graph LR
  classDef subnetwork color:#fff,fill:#555,stroke:#000,stroke-dasharray: 5 5;
  classDef vpc        color:#fff,fill:#555,stroke:#000,stroke-width:2px;

  subgraph gitlab-ci
    ci_ci[gitlab-ci/ci]:::vpc
    ci_ci_bastion(bastion subnetwork):::subnetwork
    ci_ci_runner_managers(runner-managers subnetwork):::subnetwork
    ci_ci_ep(ephemeral-runners-private subnetwork):::subnetwork
    ci_ci_esgo(ephemeral-runners-shared-gitlab-org subnetwork):::subnetwork

    ci_ci_gke[gitlab-ci/gke]:::vpc
    ci_ci_gke_gke(gke subnetwork):::subnetwork

    ci_ci_bastion --> ci_ci
    ci_ci_runner_managers --> ci_ci
    ci_ci_ep --> ci_ci
    ci_ci_esgo --> ci_ci
    ci_ci ===|peering| ci_ci_gke
    ci_ci_gke_gke --> ci_ci_gke
  end

  subgraph gitlab-production
    prd_gprd[gitlab-production/gprd]:::vpc
    prd_gprd_monitoring(monitoring-gprd subnetwork):::subnetwork

    prd_gprd_monitoring --> prd_gprd
  end

  subgraph gitlab-ci-plan-free-4
    ci_plan_free_4_ephemeral[gitlab-ci-plan-free-4/ephemeral-runners]:::vpc
    ci_plan_free_4_ephemeral_e(ephemeral-runners subnetwork):::subnetwork

    ci_plan_free_4_gke[gitlab-ci-plan-free-4/gke]:::vpc
    ci_plan_free_4_gke_gke(gke subnetwork):::subnetwork

    ci_plan_free_4_ephemeral_e --> ci_plan_free_4_ephemeral
    ci_plan_free_4_ephemeral ===|peering| ci_plan_free_4_gke
    ci_plan_free_4_gke_gke --> ci_plan_free_4_gke
  end

  subgraph gitlab-ci-plan-free-3
    ci_plan_free_3_ephemeral[gitlab-ci-plan-free-3/ephemeral-runners]:::vpc
    ci_plan_free_3_ephemeral_e(ephemeral-runners subnetwork):::subnetwork

    ci_plan_free_3_gke[gitlab-ci-plan-free-3/gke]:::vpc
    ci_plan_free_3_gke_gke(gke subnetwork):::subnetwork

    ci_plan_free_3_ephemeral_e --> ci_plan_free_3_ephemeral
    ci_plan_free_3_ephemeral ===|peering| ci_plan_free_3_gke
    ci_plan_free_3_gke_gke --> ci_plan_free_3_gke
  end

  ci_ci ===|temporary peering| prd_gprd
  ci_ci ===|peering| ci_plan_free_3_ephemeral
  ci_ci ===|peering| ci_plan_free_4_ephemeral

  linkStyle 13 stroke:#0a0,stroke-width:4px;
```

`gitlab-ci-plan-free-3` project have two networks that are peered: `ephemeral-runners` and `gke`. They are peered as
Prometheus in `gke` network needs to be able to scrape node exporter on ephemeral VMs in `ephemeral-runners` network.

As it's a [direct peering](#peering-conflicting-networks-directly), the networks can't have conflicting CIDRS.

The same goes for `gitlab-ci-plan-free-4` project.

The `ephemeral-runners` networks from `gitlab-ci-plan-free-3` and `gitlab-ci-plan-free-4` are also peered with
`ci` network in `gitlab-ci` project. This is done because runner managers in `runner-managers` subnetwork
need to be able to communicate with ephemeral VMs created in the `gitlab-ci-plan-free-X` projects.

Here we have a mix of direct peering and [peering with one hop](#peering-conflicting-networks-with-one-hop-between-them):

* `gitlab-ci/ci` and `gitlab-ci-plan-free-3/ephemeral-runners` are peered directly, so their subnetworks
  can't have conflicting CIDRs.
* `gitlab-ci/ci` and `gitlab-ci-plan-free-3/gke` are peered through `gitlab-ci-plan-free-3/ephemeral-runners`. Their
  networks also can't have conflicting CIDRs, as this would create conflict in `gitlab-ci-plan-free-3/ephemeral-runners`.

Also `gitlab-ci-plan-free-X/ephemeral-runners` are connected between each other with only one hop (`gitlab-ci/ci`),
which means that all `ephemeral-runners` subnetwork need to have unique CIDRs.

`gitlab-ci-plan-free-X/gke` are connected with more than one hop (sibling `ephemeral-runners` network -> `gitlab-ci/ci`
network -> other `ephemeral-runners` network -> other `gitlab-ci-plan-free-X/gke` network), they may have exactly the
same CIDRs.

Having the peering rules in minds we've designed such networking layout:

1. Each project used for CI runners will have a dedicated `gke` network with `gke` subnetwork. As these are
   never connected directly or with one hop, they all will use exactly the same CIDR, following the philosophy of
   "convention over configuration".

1. The `ephemeral-runners` subnetworks will be conflicting, as they all will have a one-hop common point
   in `gitlab-ci/ci`. This means that we need to make them unique across whole layout. For that we will maintain
   [a list of unique CIDRs for `ephemeral-runners` subnetworks](#ephemeral-runners-unique-cidrs-list). The rule needs
   to be followed no matter if the network is created in a dedicated project (like the `ci-plan-free-X` ones) or
   in the main `gitlab-ci` project.

1. Utility subnetworks like `bastion` or `runner-managers` need to not conflict with any other subnetworks.
   As we will have just these two subnetworks only in `gitlab-ci/ci` network,
   [we've chosen static CIDRs](#gitlab-ci-project) for them and will not change that.

1. Until we will [introduce dedicated Prometheus servers](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/13886)
   for our CI projects and integrate them with our Thanos cluster, we need to use our main Prometheus server in
   `gitlab-production` project. For that we've created and need to maintain a temporary peering between `gitlab-ci/ci`
   and `gitlab-production/gprd` networks. When creating this peering we've resolved all CIDR conflicts, so all is good
   for now and our `ephemeral-runners` CIDR creation rule should ensure we will not introduce new conflicts. We will
   however need to carefully chose the CIDR for the `gke` subnetworks, as there is one-hop peering between
   `gitlab-production/gprd` and `gitlab-ci/gke`.

#### `ephemeral-runners` unique CIDRs list

For `ephemeral-runners` subnetworks we've decided to use subsequent CIDRs, starting from `10.10.0.0/21`.

The `/21` network gives use place for 2046 nodes per network. In case we need more, we scale up the saturated
shard.

Ideally, every new CIDR should start at directly after the previously reserved one ends, although that's not
the case now.

**The list bellow is the SSOT of the CIDRs we should use!**

**Please consult every new range with it and keep this list up-to-date!**

**When adding any new ephemeral-runners subnetwork don't forget to update the
[`ci-gateway` firewall](#ci-gateway-ilb-firewall)!**

| Environment                         | Network `{$PROJECT}/$VPC/$SUBNETWORK`                  | CIDR             |
|-------------------------------------|--------------------------------------------------------|------------------|
| `GCP/gl-r-saas-l-m-amd64-gpu-1`     | `gitlab-ci/saas-l-m-gpu-s/p1`                          | `10.10.48.0/21`  |
| `GCP/gl-r-saas-l-m-amd64-gpu-2`     | `gitlab-ci/saas-l-m-gpu-s/p2`                          | `10.10.248.0/21` |
| `GCP/gl-r-saas-l-m-amd64-gpu-3`     | `gitlab-ci/saas-l-m-gpu-s/p3`                          | `10.11.8.0/21`   |
| `GCP/gitlab-r-saas-l-s-arm64-1`     | `gitlab-ci/saas-l-s-arm64/p1`                          | `10.12.48.0/21`  |
| `GCP/gitlab-r-saas-l-s-arm64-2`     | `gitlab-ci/saas-l-s-arm64/p2`                          | `10.12.56.0/21`  |
| `GCP/gitlab-r-saas-l-s-arm64-3`     | `gitlab-ci/saas-l-s-arm64/p3`                          | `10.12.64.0/21`  |
| `GCP/gitlab-r-saas-l-s-arm64-4`     | `gitlab-ci/saas-l-s-arm64/p4`                          | `10.12.112.0/21` |
| `GCP/gitlab-r-saas-l-s-arm64-5`     | `gitlab-ci/saas-l-s-arm64/p5`                          | `10.12.120.0/21` |
| `GCP/gitlab-r-saas-l-s-arm64-6`     | `gitlab-ci/saas-l-s-arm64/p6`                          | `10.12.128.0/21` |
| `GCP/gitlab-ci`                     | `gitlab-ci/saas-l-p-amd64/psc`                         | `10.12.0.0/24`   |
| `GCP/gitlab-r-saas-l-p-amd64-1`     | `gitlab-ci/saas-l-p-amd64/p1`                          | `10.12.8.0/21`   |
| `GCP/gitlab-r-saas-l-p-amd64-2`     | `gitlab-ci/saas-l-p-amd64/p2`                          | `10.12.16.0/21`  |
| `GCP/gitlab-r-saas-l-p-amd64-3`     | `gitlab-ci/saas-l-p-amd64/p3`                          | `10.12.24.0/21`  |
| `GCP/gitlab-r-saas-l-p-amd64-4`     | `gitlab-ci/saas-l-p-amd64/p4`                          | `10.12.72.0/21`  |
| `GCP/gitlab-r-saas-l-p-amd64-5`     | `gitlab-ci/saas-l-p-amd64/p5`                          | `10.12.80.0/21`  |
| `GCP/gitlab-r-saas-l-p-amd64-6`     | `gitlab-ci/saas-l-p-amd64/p6`                          | `10.12.88.0/21`  |
| `GCP/gitlab-r-saas-l-p-amd64-7`     | `gitlab-ci/saas-l-p-amd64/p7`                          | `10.12.96.0/21`  |
| `GCP/gitlab-r-saas-l-p-amd64-8`     | `gitlab-ci/saas-l-p-amd64/p8`                          | `10.12.104.0/21` |
| `GCP/gitlab-r-saas-l-p-amd64-9`     | `gitlab-ci/saas-l-p-amd64/p9`                          | `10.12.136.0/21` |
| `GCP/gitlab-r-saas-l-m-amd64-1`     | `gitlab-ci/saas-l-m-amd64/p1`                          | `10.13.64.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-2`     | `gitlab-ci/saas-l-m-amd64/p2`                          | `10.13.72.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-3`     | `gitlab-ci/saas-l-m-amd64/p3`                          | `10.13.80.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-4`     | `gitlab-ci/saas-l-m-amd64/p4`                          | `10.13.88.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-5`     | `gitlab-ci/saas-l-m-amd64/p5`                          | `10.13.96.0/21`  |
| `GCP/gitlab-r-saas-l-l-amd64-1`     | `gitlab-ci/saas-l-l-amd64/p1`                          | `10.13.104.0/21` |
| `GCP/gitlab-r-saas-l-l-amd64-2`     | `gitlab-ci/saas-l-l-amd64/p2`                          | `10.13.112.0/21` |
| `GCP/gitlab-r-saas-l-l-amd64-3`     | `gitlab-ci/saas-l-l-amd64/p3`                          | `10.13.120.0/21` |
| `GCP/gitlab-r-saas-l-l-amd64-4`     | `gitlab-ci/saas-l-l-amd64/p4`                          | `10.13.128.0/21` |
| `GCP/gitlab-r-saas-l-l-amd64-5`     | `gitlab-ci/saas-l-l-amd64/p5`                          | `10.13.136.0/21` |
| `GCP/gitlab-r-saas-l-xl-amd64-1`    | `gitlab-ci/saas-l-xl-amd64/p1`                         | `10.13.144.0/21` |
| `GCP/gitlab-r-saas-l-xl-amd64-2`    | `gitlab-ci/saas-l-xl-amd64/p2`                         | `10.13.152.0/21` |
| `GCP/gitlab-r-saas-l-xl-amd64-3`    | `gitlab-ci/saas-l-xl-amd64/p3`                         | `10.13.160.0/21` |
| `GCP/gitlab-r-saas-l-xl-amd64-4`    | `gitlab-ci/saas-l-xl-amd64/p4`                         | `10.13.168.0/21` |
| `GCP/gitlab-r-saas-l-xl-amd64-5`    | `gitlab-ci/saas-l-xl-amd64/p5`                         | `10.13.176.0/21` |
| `GCP/gitlab-r-saas-l-2xl-amd64-1`   | `gitlab-ci/saas-l-2xl-amd64/p1`                        | `10.13.184.0/21` |
| `GCP/gitlab-r-saas-l-2xl-amd64-2`   | `gitlab-ci/saas-l-2xl-amd64/p2`                        | `10.13.192.0/21` |
| `GCP/gitlab-r-saas-l-2xl-amd64-3`   | `gitlab-ci/saas-l-2xl-amd64/p3`                        | `10.13.200.0/21` |
| `GCP/gitlab-r-saas-l-2xl-amd64-4`   | `gitlab-ci/saas-l-2xl-amd64/p4`                        | `10.13.208.0/21` |
| `GCP/gitlab-r-saas-l-2xl-amd64-5`   | `gitlab-ci/saas-l-2xl-amd64/p5`                        | `10.13.216.0/21` |
| `GCP/gitlab-r-saas-l-m-arm64-1`     | `gitlab-ci/saas-l-m-arm64/p1`                          | `10.13.224.0/21` |
| `GCP/gitlab-r-saas-l-m-arm64-2`     | `gitlab-ci/saas-l-m-arm64/p2`                          | `10.13.232.0/21` |
| `GCP/gitlab-r-saas-l-m-arm64-3`     | `gitlab-ci/saas-l-m-arm64/p3`                          | `10.13.240.0/21` |
| `GCP/gitlab-r-saas-l-m-arm64-4`     | `gitlab-ci/saas-l-m-arm64/p4`                          | `10.13.16.0/21`  |
| `GCP/gitlab-r-saas-l-m-arm64-5`     | `gitlab-ci/saas-l-m-arm64/p5`                          | `10.13.24.0/21`  |
| `GCP/gitlab-r-saas-l-m-arm64-6`     | `gitlab-ci/saas-l-m-arm64/p6`                          | `10.13.32.0/21`  |
| `GCP/gitlab-r-saas-l-l-arm64-1`     | `gitlab-ci/saas-l-l-arm64/p1`                          | `10.13.248.0/21` |
| `GCP/gitlab-r-saas-l-l-arm64-2`     | `gitlab-ci/saas-l-l-arm64/p2`                          | `10.14.0.0/21`   |
| `GCP/gitlab-r-saas-l-l-arm64-3`     | `gitlab-ci/saas-l-l-arm64/p3`                          | `10.14.8.0/21`   |
| `GCP/gitlab-r-saas-l-l-arm64-4`     | `gitlab-ci/saas-l-l-arm64/p4`                          | `10.15.0.0/21`   |
| `GCP/gitlab-r-saas-l-l-arm64-5`     | `gitlab-ci/saas-l-l-arm64/p5`                          | `10.15.8.0/21`   |
| `GCP/gitlab-r-saas-l-l-arm64-6`     | `gitlab-ci/saas-l-l-arm64/p6`                          | `10.15.16.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-org-1` | `gitlab-ci/saas-l-m-amd64-org/p1`                      | `10.14.16.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-org-2` | `gitlab-ci/saas-l-m-amd64-org/p2`                      | `10.14.24.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-org-3` | `gitlab-ci/saas-l-m-amd64-org/p3`                      | `10.14.32.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-org-4` | `gitlab-ci/saas-l-m-amd64-org/p4`                      | `10.14.40.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-org-5` | `gitlab-ci/saas-l-m-amd64-org/p5`                      | `10.14.48.0/21`  |
| `GCP/gitlab-r-saas-l-m-amd64-org-6` | `gitlab-ci/saas-l-m-amd64-org/p6`                      | `10.14.56.0/21`  |
| `GCP/gitlab-r-saas-l-s-amd64-1`     | `gitlab-ci/saas-l-s-amd64/p1`                          | `10.14.64.0/21`  |
| `GCP/gitlab-r-saas-l-s-amd64-2`     | `gitlab-ci/saas-l-s-amd64/p2`                          | `10.14.72.0/21`  |
| `GCP/gitlab-r-saas-l-s-amd64-3`     | `gitlab-ci/saas-l-s-amd64/p3`                          | `10.14.80.0/21`  |
| `GCP/gitlab-r-saas-l-s-amd64-4`     | `gitlab-ci/saas-l-s-amd64/p4`                          | `10.14.88.0/21`  |
| `GCP/gitlab-r-saas-l-s-amd64-5`     | `gitlab-ci/saas-l-s-amd64/p5`                          | `10.14.96.0/21`  |
| `GCP/gitlab-r-saas-l-s-amd64-6`     | `gitlab-ci/saas-l-s-amd64/p6`                          | `10.14.104.0/21` |
| `GCP/gitlab-r-saas-l-s-amd64-7`     | `gitlab-ci/saas-l-s-amd64/p7`                          | `10.14.112.0/21` |
| `GCP/gitlab-r-saas-l-s-amd64-8`     | `gitlab-ci/saas-l-s-amd64/p8`                          | `10.14.120.0/21` |
| `GCP/gitlab-r-saas-l-s-amd64-9`     | `gitlab-ci/saas-l-s-amd64/p9`                          | `10.14.128.0/21` |
| `AWS/r-saas-m-staging`              | `jobs-vpc/saas-macos-staging-blue-1`                   | `10.20.0.0/21`   |
| `AWS/r-saas-m-staging`              | `jobs-vpc/saas-macos-staging-blue-2`                   | `10.20.8.0/21`   |
| `AWS/r-saas-m-staging`              | `jobs-vpc/saas-macos-staging-green-1`                  | `10.20.16.0/21`  |
| `AWS/r-saas-m-staging`              | `jobs-vpc/saas-macos-staging-green-2`                  | `10.20.24.0/21`  |
| `AWS/r-saas-m-m1`                   | `jobs-vpc/saas-macos-m1-blue-1`                        | `10.30.0.0/21`   |
| `AWS/r-saas-m-m1`                   | `jobs-vpc/saas-macos-m1-blue-2`                        | `10.30.8.0/21`   |
| `AWS/r-saas-m-m1`                   | `jobs-vpc/saas-macos-m1-green-1`                       | `10.30.16.0/21`  |
| `AWS/r-saas-m-m1`                   | `jobs-vpc/saas-macos-m1-green-2`                       | `10.30.24.0/21`  |
| `AWS/r-saas-m-l-m2pro`              | `jobs-vpc/saas-macos-l-m2pro-blue-1`                   | `10.40.0.0/21`   |
| `AWS/r-saas-m-l-m2pro`              | `jobs-vpc/saas-macos-l-m2pro-blue-2`                   | `10.40.8.0/21`   |
| `AWS/r-saas-m-l-m2pro`              | `jobs-vpc/saas-macos-l-m2pro-green-1`                  | `10.40.16.0/21`  |
| `AWS/r-saas-m-l-m2pro`              | `jobs-vpc/saas-macos-l-m2pro-green-2`                  | `10.40.24.0/21`  |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-vanilla`          | `10.44.0.0/19`   |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-vanilla-services` | `10.44.32.0/19`  |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-vanilla-pods`     | `10.44.64.0/19`  |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-vanilla-runner`   | `10.44.96.0/19`  |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-kata`             | `10.44.128.0/19` |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-kata-services`    | `10.44.160.0/19` |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-kata-pods`        | `10.44.192.0/19` |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-kata-runner`      | `10.44.224.0/19` |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-gvisor`           | `10.45.0.0/19`   |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-gvisor-services`  | `10.45.32.0/19`  |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-gvisor-pods`      | `10.45.64.0/19`  |
| `GCP/gitlab-ci`                     | `gitlab-ci/experimental/experimental-gvisor-runner`    | `10.45.96.0/19`  |

##### `ci-gateway` ILB firewall

When updating the `ephemeral-runners` CIDRs please remember to update the firewall rules for
the `ci-gateway` ILBs.

The rules are managed with Terraform in GPRD and GSTG environments within the `google_compute_firewall` resource
named `ci-gateway-allow-runners`.

The GPRD (GitLab.com) definition can be found [here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/743cf13a31633a62f9e6e8b67abeee3d151792ed/environments/gprd/main.tf#L2960).

The GSTG (staging.gitlab.com) definition can be found [here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/743cf13a31633a62f9e6e8b67abeee3d151792ed/environments/gstg/main.tf#L2957)

When doing any changes related to ephemeral runners make sure to check which GitLab environments that runner
supports (for example our `private` runners support both GPRD and GSTG while `shared` only GPRD) and update
the firewall rules respectively.

### GCP projects

Here you can find details about networking in different projects used by CI Runners service.

#### gitlab-ci project

| Network Name   | Subnet Name                 | CIDR            | Purpose                                                                                                                 |
| -------------- | --------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `default`      | `default`                   | `10.142.0.0/20` | all non-runner machines (managers, prometheus, etc.). In `us-east1` - we don't use this subnetwork in any other region. |
| `ci`           | `sd-exporter-ci`            | `10.142.16.0/24`| Monitoring subnetwork                                                                                                   |
| `ci`           | `bastion-ci`                | `10.1.4.0/24`   | Bastion network                                                                                                         |
| `ci`           | `runner-managers`           | `10.1.5.0/24`   | Network for Runner Managers ([new ones](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/456))                     |
| `runners-gke`  | `runners-gke`               | `10.9.4.0/24`   | Primary; GKE nodes range                                                                                                |
| `runners-gke`  | `runners-gke`               | `10.8.0.0/16`   | Secondary; GKE pods range                                                                                               |
| `runners-gke`  | `runners-gke`               | `10.9.0.0/22`   | secondary; GKE services range                                                                                           |

The `default` network will be removed once we will move all of the runner managers to a new
infrastructure, which is being tracked [by this epic](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/456).

The `ci` network will be getting new subnetworks for `ephemeral-runners-X` while working on
[this epic](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/456).

The `runners-gke` network, at least for now, is in the expected state.

#### gitlab-ci-windows project

| Network Name   | Subnet Name          | CIDR          | Purpose                           |
| -------------- | -------------------- | ------------- | --------------------------------- |
| `windows-ci`   | `manager-subnet`     | `10.1.0.0/16` | Runner manager machines           |
| `windows-ci`   | `executor-subnet`    | `10.2.0.0/16` | Ephemeral runner machines         |
| `windows-ci`   | `runner-windows-ci`  | `10.3.0.0/24` | Runner network for ansible/packer |
| `windows-ci`   | `bastion-windows-ci` | `10.3.1.0/24` | bastion network                   |

Windows project will most probably get the `runners-gke` network and GKE based monitoring in the future. This
is however not yet scheduled.

### `ci-gateway` Internal Load Balancers

To reduce the amount of traffic that goes through the public Internet (which causes additional costs)
and to add a little performance improvements, Runner managers and Git are set to use internal
load balancers which routes the traffic through GCP internal networking.

For that we've created a special VPC named `ci-gateway`. Dedicated VPC was added to avoid
peering with the main VPC of GitLab backend - for security reasons and to reduce the number
of possible CIDRs collisions.

This configuration was first tested with `private` runners shard and `staging.gitlab.com`. And
next was replicated in GPRD - for `gitlab.com` and with the three Linux runners shards we have.

```mermaid
graph LR
  subgraph project::GSTG
    subgraph VPC::gstg::gstg
      gstg_haproxy_b(HaProxy us-east1-b)
      gstg_haproxy_c(HaProxy us-east1-c)
      gstg_haproxy_d(HaProxy us-east1-d)

      gstg_gitlab_backends(GitLab backend services)

      gstg_haproxy_b -->|routes direct without peering| gstg_gitlab_backends
      gstg_haproxy_c -->|routes direct without peering| gstg_gitlab_backends
      gstg_haproxy_d -->|routes direct without peering| gstg_gitlab_backends
    end

    subgraph VPC::gstg::ci-gateway
      gstg_ci_gateway_ILB_b(ILB us-east1-b)
      gstg_ci_gateway_ILB_c(ILB us-east1-c)
      gstg_ci_gateway_ILB_d(ILB us-east1-d)
    end

    gstg_ci_gateway_ILB_b -->|routes direct without peering| gstg_haproxy_b
    gstg_ci_gateway_ILB_c -->|routes direct without peering| gstg_haproxy_c
    gstg_ci_gateway_ILB_d -->|routes direct without peering| gstg_haproxy_d
  end

  subgraph project::GPRD
    subgraph VPC::gprd::gprd
      gprd_haproxy_b(HaProxy us-east1-b)
      gprd_haproxy_c(HaProxy us-east1-c)
      gprd_haproxy_d(HaProxy us-east1-d)

      gprd_gitlab_backends(GitLab backend services)

      gprd_haproxy_b -->|routes direct without peering| gprd_gitlab_backends
      gprd_haproxy_c -->|routes direct without peering| gprd_gitlab_backends
      gprd_haproxy_d -->|routes direct without peering| gprd_gitlab_backends
    end

    subgraph VPC::gprd::ci-gateway
      gprd_ci_gateway_ILB_b(ILB us-east1-b)
      gprd_ci_gateway_ILB_c(ILB us-east1-c)
      gprd_ci_gateway_ILB_d(ILB us-east1-d)
    end

    gprd_ci_gateway_ILB_b -->|routes direct without peering| gprd_haproxy_b
    gprd_ci_gateway_ILB_c -->|routes direct without peering| gprd_haproxy_c
    gprd_ci_gateway_ILB_d -->|routes direct without peering| gprd_haproxy_d
  end

  subgraph project::gitlab-ci
    subgraph VPC::gitlab-ci::ci
      subgraph runner-managers
        runners_manager_private_1[runners-manager-private-1]
        runners_manager_private_2[runners-manager-private-2]
        runners_manager_private_3[runners-manager-private-3]

        runners_manager_shared_gitlab_org_X[runners-manager-shared-gitlab-org-X]

        runners_manager_shared_X[runners-manager-shared-X]
      end

      subgraph example-ephemeral-vms
        private_ephemeral_vm_1
        private_ephemeral_vm_2
        shared_gitlab_org_ephemeral_vm
      end

      runners_manager_private_1 -->|manages a job on| private_ephemeral_vm_1
      runners_manager_private_2 -->|manages a job on| private_ephemeral_vm_2

      runners_manager_shared_gitlab_org_X -->|manages a job on| shared_gitlab_org_ephemeral_vm
    end
  end

  subgraph project::gitlab-ci-plan-free-X
    subgraph VPC::gitlab-ci-plan-free-X::ephemeral-runners
      shared_ephemeral_vm
    end
  end

  runners_manager_shared_X --> shared_ephemeral_vm

  runners_manager_private_1 -->|connects through VPC peering| gstg_ci_gateway_ILB_c
  runners_manager_private_2 -->|connects through VPC peering| gstg_ci_gateway_ILB_d
  runners_manager_private_3 -->|connects through VPC peering| gstg_ci_gateway_ILB_b

  runners_manager_private_1 -->|connects through VPC peering| gprd_ci_gateway_ILB_c
  runners_manager_private_2 -->|connects through VPC peering| gprd_ci_gateway_ILB_d
  runners_manager_private_3 -->|connects through VPC peering| gprd_ci_gateway_ILB_b

  runners_manager_shared_gitlab_org_X -->|connects through VPC peering| gprd_ci_gateway_ILB_c

  runners_manager_shared_X -->|connects through VPC peering| gprd_ci_gateway_ILB_d

  private_ephemeral_vm_1 -->|connects through VPC peering| gstg_ci_gateway_ILB_c
  private_ephemeral_vm_2 -->|connects through VPC peering| gprd_ci_gateway_ILB_d

  shared_gitlab_org_ephemeral_vm -->|connects through VPC peering| gprd_ci_gateway_ILB_c

  shared_ephemeral_vm -->|connects through VPC peering| gprd_ci_gateway_ILB_d
```

#### How it's configured

The above diagram shows a general view of how this configuration is set up.

In both GSTG and GPRD projects we've created a dedicated VPC named `ci-gateway`. This VPC
contains Internal Load Balancers (ILBs) available on defined FQDNs. The VPCs are peered with
CI VPCs that contain runner managers and ephemeral VMs on which the jobs are executed.

As an ILB can route traffic only to nodes in the same VPC, we had to add a small change
to our HaProxy configuration. We've created a dedicated cluster of new HaProxy nodes
provisioned with two network interfaces: in `gprd` and in `ci-gateway` VPCs. The same
configuration is created in GSTG.

HaProxy got a new frontend named `https_git_ci_gateway` and listening on port `8989`. This
fronted passes the detected `git+https` traffic and a limited amount of API endpoints (purely
for Runner communication, which includes requesting for a job, sending trace update and sending
job update) to GitLab backends. Other requests are redirected with `307` HTTP response code
to `staging.gitlab.com` or `gitlab.com` - depending on the requested resource.

To reduce the cost that is created by traffic made across availability zones, in each project
we have three ILBs - one for each availability zone (`us-east1-b`, `us-east1-c` and `us-east1-d`)
used by the CI fleet in the `us-east1` region. Each ILB is configured to target HaProxy nodes
only in its availability zone.

For that, the following FQDNs were created:

* `git-us-east1-b.ci-gateway.int.gstg.gitlab.net`
* `git-us-east1-c.ci-gateway.int.gstg.gitlab.net`
* `git-us-east1-d.ci-gateway.int.gstg.gitlab.net`
* `git-us-east1-b.ci-gateway.int.gprd.gitlab.net`
* `git-us-east1-c.ci-gateway.int.gprd.gitlab.net`
* `git-us-east1-d.ci-gateway.int.gprd.gitlab.net`

Runner nodes are configured to point the ILBs with the `url` and `clone_url` settings.
As we set our runners to operate in a specific availability zone, each of them
points the relevant ILB FQDN.

#### How it works

GitLab Runner is configured to talk with the dedicated ILB. Communication goes through
the VPC peering and reaches one of the HaProxy nodes backing the ILB. TLS certificate
is verified and Runner saves this information to configure Git in the job environment.

When job is received, Runner starts executing it on the ephemeral VM. It configures
Git to use the CAChain resolved from initial API request. Repo URL is configured to
use the ILB as GitLab's endpoint.

When job reaches the step in which sources are updated, `git clone` operation is
executed against the ILB. Communication again goes through the VPC peering and reaches
one of the HaProxy nodes. TLS certificate is verified using the CAChain resolved
earlier.

When job reaches the step when artifact needs to be downloaded or uploaded, it
also tries to talk with the ILB. However, HaProxy frontend detects that this
communication is unsupported and redirects it to the public Internet gateway
of GitLab instance that the job belongs to.

In the meantime, Runner receives job logs and transfers them back - together
with updating the status of the job - to GitLab's API. For that the communication
through VPC peering and the dedicaed ILB is used as well.
