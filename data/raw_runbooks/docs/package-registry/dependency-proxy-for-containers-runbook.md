# Dependency proxy for containers runbook

## Summary

The Dependency Proxy for GitLab Container Registry acts as a local proxy for frequently accessed Docker images from Docker Hub.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

### API

* `v2/:group_id/dependency_proxy/containers/:image/manifests/*tag`
* `v2/:group_id/dependency_proxy/containers/:image/blobs/:sha`
* `v2/:group_id/dependency_proxy/containers/:image/blobs/:sha/upload/authorize`
* `v2/:group_id/dependency_proxy/containers/:image/blobs/:sha/upload`
* `v2/:group_id/dependency_proxy/containers/:image/manifests/*tag/upload/authorize`
* `v2/:group_id/dependency_proxy/containers/:image/manifests/*tag/upload`

## Observability

* [Dependency Proxy Dashboard](https://log.gprd.gitlab.net/app/r/s/dQP4i)
* [Dependency Proxy Statistics](https://log.gprd.gitlab.net/app/r/s/vAiWj)

## Troubleshooting

* [General troubleshooting issues](https://docs.gitlab.com/ee/user/packages/dependency_proxy/#troubleshooting)

## Service Changes

* [Recent MR's relating to Dependency Proxy](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/?sort=merged_at_desc&state=merged&search=dependency%20proxy&first_page_size=20)
* [Docker Hub changelog](https://docs.docker.com/release-notes/)
* [Docker Hub usage and limits](https://docs.docker.com/docker-hub/usage/)

## Common Operations

### Test Docker pull through proxy

`docker pull $GITLAB_HOST:$PORT/$GROUP_PATH/dependency_proxy/containers/library/alpine:latest`

## References

* [User Guide](https://docs.gitlab.com/ee/user/packages/dependency_proxy/)
* [API Documentation](https://docs.gitlab.com/api/dependency_proxy/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/dependency_proxy)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/dependency_proxy)
* [Local setup](https://gitlab.com/gitlab-org/gitlab-development-kit/-/blob/main/doc/howto/dependency_proxy.md)
* [Authentication and authorization](https://docs.gitlab.com/development/packages/dependency_proxy/#authentication-and-authorization)
* [Workhorse for file handling](https://docs.gitlab.com/development/packages/dependency_proxy/#workhorse-for-file-handling)
