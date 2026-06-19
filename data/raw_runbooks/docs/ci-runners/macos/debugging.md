# Debugging macOS Runners

This document provides a comprehensive guide for debugging issues with AWS macOS runner instances. It covers monitoring instance health, accessing instances, debugging nested VMs, and handling common problems.

## Known Issues

- [Host Acquisition Problems](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/254): Extended wait times for host availability
- [job VM Performance Variance](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/223): Historical I/O performance issues (resolved)
- **Extended Wait Times**: Deployments have been delayed by hours or days waiting for capacity.

## Performance Considerations

Historical performance issues, especially with I/O variance, were traced to EBS lazy loading of large AMI images. The current architecture addresses this by:

1. Using dedicated EBS volumes for job VM disks
1. Pre-downloading images at startup
1. Ensuring full EBS performance from the start

For detailed performance characteristics, see [AWS EBS documentation](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html).

## Monitoring Scaling Progress and Failures

### Auto Scaling Group Health Monitoring

#### **Checking ASG Progress**

1. **AWS Console ASG View**
    - Navigate to [AWS Console Auto Scaling Groups](https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1#AutoScalingGroups:)
    - Select the relevant ASG (medium or large Macs)
    - Check **Activity** tab for scaling events

2. **Common Scaling Activity Statuses**
    - **Successful**: Green checkmark with completion timestamp
    - **In Progress**: Yellow icon with "Scaling" status
    - **Failed**: Red X with error description. For example, "Insufficient capacity"

## Determining autoscaling group (ASG) health

### Health Metrics and Monitoring

#### **AWS ASG dashboard**

- Access via [AWS Console](https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1#AutoScalingGroups:)
  - Staging Macs are in account `251165465090`
  - Medium Macs are in account `215928322474`
  - Large Macs are in account `730335264460`
- Check for instances in unhealthy states
- Check scaling activity history for unexpected terminations or failed operations

#### **Mac host metrics**

- Check the [EC2 Dedicated Hosts dashboard](https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1#Hosts:) for abnormal states
- Monitor for hosts in "pending" or "released" states that might indicate provisioning issues
- Verify vCPU utilization is present for all active hosts

#### **Runner manager metrics**

- [Grafana dashboard](https://dashboards.gitlab.net/d/ci-runners-deployment/ci-runners3a-deployment-overview?from=now-3h&orgId=1&refresh=5m&timezone=utc&to=now&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-project_jobs_running=$__all&var-runner_job_failure_reason=$__all&var-shard=saas-macos-staging&var-shard=saas-macos-medium-m1&var-shard=saas-macos-large-m2pro&var-stage=main&var-type=ci-runners)

#### **Logs Location**

- Nesting logs: `/Users/ec2-user/nesting.log`
- macOS init logs (from `user-data` script on Mac host): `/var/log/amazon/ec2/ec2-macos-init.log`

## Access to macOS instances and job VMs

Refer to [access.md](./access.md) for information on how to access macOS instances and job VMs.

## Debugging connection between runner manager and host Mac

- Confirm established connection with host Mac

    ```shell
    # On runner manager
    ss -tn | grep HOST_MAC_PRIVATE_IP4
    ```

- Confirm established connections from host Mac to runner manager

    ```shell
    # On the host Mac
    sudo lsof -i@RUNNER_MANAGER_PRIVATE_IP4
    ```

- List network connections between the macOS host instance and nesting job VMs. For every job VM in `nesting list` there should be a connection.

    ```shell
    # On the host Mac
    sudo lsof -i@127.0.0.1 | grep nesting
    ```

## Debugging Nesting Client/Server

### Logs Locations

- Nesting settings

  ```
  # On the host Mac
  cat /Users/ec2-user/nesting.json
  ```

- List available nesting images

  ```
  # On the host Mac
  ls /Volumes/VMData/images
  ```

## Managing Nested Job VMs with Nesting client

### Confirm nesting service is running

```shell
# On the host Mac
launchctl list | grep nesting
```

### Get nesting help

```shell
# On the host Mac
nesting
```

### Get nesting version

```shell
# On the host Mac
nesting version
```

### List running job VMs

```shell
# On the host Mac
nesting list
```

Output will provide the ID, image, and localhost:port of the running job VM. For example:

```shell
bb9wtbcq macos-14-xcode-15 127.0.0.1:60835
```

### SSH from macOS instance into job VM

The SSH userid and password for job VMs can be found in the associated runner manager instance in the `[runners.autoscaler.vm_isolation.connector_config]` section of `/etc/gitlab-runner/config.toml`.

```shell
# On the host Mac
ssh -p PORT userid@127.0.0.1
```

### Possible Nesting Issues

1. Service not starting

   ```
   # Restart the nesting server
   sudo launchctl unload /Library/LaunchDaemons/nesting.plist
   sudo launchctl load /Library/LaunchDaemons/nesting.plist
   ```

1. Connection issues

   ```
   # Check network connectivity
   sudo tcpdump -i any port 22 | grep RUNNER_MANAGER_PRIVATE_IP4
   ```
