# Patch Cell's Tenant Model

## Overview

Changes to a Cell's `TENANT_MODEL` are applied through a [JSON Patch (RFC 6902)](https://datatracker.ietf.org/doc/html/rfc6902). Patches are applied from inner rings to outer rings, starting with `ring 0` and proceeding outward sequentially.

If a patch application fails at any ring, the entire process halts and requires manual intervention.

> [!note]
> Patches are not applied to the quarantine ring (-1). To update the `TENANT_MODEL` of a Cell in the quarantine ring, open a Merge Request and update it directly.

## Prerequisites

- Configure [`ringctl` in your environment](https://gitlab.com/gitlab-com/gl-infra/ringctl#preparing-your-environment)
- Ensure you have access to [`cells/tissue`](https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/)

## Patch Operations

The following patch operations are available using [`ringctl`](https://gitlab.com/gitlab-com/gl-infra/ringctl):

| Operation | Description                           | Parameters                       |
| --------- | ------------------------------------- | -------------------------------- |
| `add`     | Add a new field to the `TENANT_MODEL` | Target path, Value               |
| `replace` | Replace a field's value               | Target JSON path, Value          |
| `remove`  | Remove a field                        | JSON path                        |
| `move`    | Move a field to a new location        | Source path, Destination path    |
| `copy`    | Copy a field to a new location        | Source path, Destination path    |

## Guides

- [Creating Patches](creating.md) - How to create and submit patches
- [Debugging Patches](debugging.md) - How to check patch status and debug failures
- [Deleting a Patch](deleting.md) - How to delete a patch
- [Retrying a Failed Patch](retrying.md) - How to retry a failed patch
- [Connecting to a Cell's Toolbox Pod](../toolbox.md) - How to access a cell for advanced troubleshooting
