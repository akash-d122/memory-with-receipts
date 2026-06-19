# Docker machine fails to create machine

## `bad certificate`

This usually means that the certificates in
`/root/.docker/machine/certs` has expired and we are facing
<https://gitlab.com/gitlab-org/gitlab-runner/-/issues/3676>.

1. Verify the certs were recently created.

    ```shell
    sudo ls -lah /root/.docker/machine/certs/
    total 24K
    drwx------ 2 root root 4.0K May 20 07:31 .
    drwxr-xr-x 4 root root 4.0K May 20 07:31 ..
    -rw------- 1 root root 1.7K May 20 07:31 ca-key.pem
    -rw-r--r-- 1 root root 1.1K May 20 07:31 ca.pem
    -rw-r--r-- 1 root root 1.1K May 20 07:31 cert.pem
    -rw------- 1 root root 1.7K May 20 07:31 key.pem
    ```

1. Stop `gitlab-runner` which shouldn't be running any jobs.

    ```shell
    sudo /root/runner_upgrade.sh stop
    ```

1. Delete idle machines

    ```shell
    sudo ls /root/.docker/machine/machines | xargs -P100 -n1 sudo -H docker-machine rm -f
    ```

1. Move old certificates to another directory just in case.

    ```shell
    sudo mv /root/.docker/machine/certs/ /tmp/certs.bak
    ```

1. Run `docker-machine create` to force certificate creation. To look at
what flags to pass you can look at `/etc/gitlab-runner/config.toml` to
see what flags are defined.

    ```shell
    sudo -H docker-machine create --driver google \
        --google-project xx \
        --google-username=xx \
        --google-use-internal-ip --google-zone=xx \
        --google-service-account=xxx \
        --google-machine-image=xx \
        --google-subnetwork=xx --google-network=xx \
        vm01
    ```

1. Start `gitlab-runner`

    ```shell
    sudo /root/runner_upgrade.sh
    ```
