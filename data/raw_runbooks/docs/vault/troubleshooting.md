# Troubleshooting Hashicorp Vault

## No Active Vault Instance / Vault Sealed / Vault Low Failure Tolerance

The Vault pods are failing to start, have lost quorum or are unable to auto-unseal.

Vault is deployed in a cluster of 5 nodes, so it needs at least 3 healthy nodes to have a quorum and be operational.

Check the status of the Vault deployment and investigate any failing pod for errors:

```sh
kubectl --namespace vault get pods
kubectl --namespace vault logs vault-X
```

You can also [check the logs in Elasticsearch](https://nonprod-log.gitlab.net/goto/225b16e0-0687-11ed-af31-918941b0065a) instead.

In case of unseal errors:

- Verify that the Kubernetes Service Account is still associated to its Google Service Account `vault-ops-k8s@gitlab-ops.iam.gserviceaccount.com`:

  ```sh
  kubectl --namespace vault describe serviceaccount vault
  ```

- Verify that this Service Account has permission to use the [unseal KMS key](https://console.cloud.google.com/security/kms/key/manage/global/gitlab-vault-vault-production/vault-vault-production-unseal-key;tab=overview?project=gitlab-vault-production) for encryption/decryption.

## Vault Audit Log Request Failure

Vault is unable to send its audit log and thus has stopped all operations until it is able again.

At the time of this writing, [the Vault audit logs are written directly to `stdout`](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/vault-configuration/-/blob/master/audit.tf), so they can be collected by Fluentd and shipped to Elasticsearch, which makes failure extremely unlikely.

If Vault fails to write its audit logs it could mean:

- a bug introduced in Vault: has it been upgraded recently? Search the [issues on GitHub](https://github.com/hashicorp/vault/issues).
- `containerd` not able to handle the container's output, possibly affecting other workloads, check the health of node running the active Vault pod.
