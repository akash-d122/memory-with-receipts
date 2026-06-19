## db-benchmarking bastion hosts

### How to start using them

SSH config is managed via `glsh ssh-config` ([details](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26738)).

Once your config is in place, test it by ssh'ing to the jmeter host:

```
ssh jmeter-01-inf-db-benchmarking.c.gitlab-db-benchmarking.internal
```
