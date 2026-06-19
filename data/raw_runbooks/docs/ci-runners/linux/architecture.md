## Linux CI Runners: Architecture

The GitLab CI GCP Project is the top level project for CI Runner Managers categorized as size—small, medium, and large. Each Runner Manager is responsible for overseeing a set of ephemeral VMs used to execute CI jobs.
These ephemeral VMs are grouped into separate clusters, designated as Small-1 to Small-N, Medium-1 to Medium-N, and Large-1 to Large-N, each capable of handling a different load of CI tasks, indicated by the varying numbers of VMs for each shard.
The architecture employs VPC Peering to establish network connectivity between the Runner Managers and the corresponding VM clusters, ensuring a segregated and secure network environment for each set of CI tasks. This design is optimized for resource utilization, allowing for efficient scaling according to the demands.

Refer to the high-level architecture diagram below ![](architecture.png)
