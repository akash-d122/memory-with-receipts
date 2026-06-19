# Pulp Runbook - Deleting a Package

## Overview

Deleting a package from Pulp is a multi-step process. Pulp tracks content by
an internal `pulp_href` identifier, and package removal requires explicitly
modifying repository content rather than deleting the package directly.

This runbook covers how to remove a package from a Pulp RPM repository. The
package content artifact is not deleted from Pulp storage - it is only removed
from the target repository version going forward. Existing repository versions
that included the package remain unchanged (Pulp repository versions are
immutable).

## Prerequisites

- [Pulp CLI configured and authenticated](./README.md#configuration)

## Usage

Run [scripts/pulp/delete-package.sh](../../scripts/pulp/delete-package.sh) with a partial package name and partial repository name. An optional `--profile` flag selects a Pulp CLI profile. Use `--dry-run` to verify the search resolves to the correct package and repository before making any changes:

```bash
scripts/pulp/delete-package.sh --package <search> --repository <search> [--profile <profile>] [--dry-run]
```

Examples:

```bash
scripts/pulp/delete-package.sh --package gitlab-ee-18.9.1 --repository sles-12.5-x86_64
scripts/pulp/delete-package.sh --package gitlab-ee-18.9.1 --repository sles-12.5-x86_64 --profile ops
scripts/pulp/delete-package.sh --package gitlab-ee-18.9.1 --repository sles-12.5-x86_64 --dry-run
```

> [!NOTE]
> If the search terms match more than one package or repository, the script will print the matches and exit with an error asking you to be more specific.
> This is intentional to make sure that there is only one package deleted at one time, since this action is destructive.

The script will:

1. Look up the package href by filename
2. Remove the package from the repository
3. Verify the package is absent from the latest repository version
4. Clean up the orphaned content artifact from storage using `orphan cleanup --content-hrefs`

**Warning:** Avoid running `pulp orphan cleanup` without `--content-hrefs` as
it will delete all unreferenced content across all repositories.

If you do not know the exact repository name, search by partial name first:

```bash
pulp repository list --name-contains '<partial-name>'
```

## Notes

- **Repository version history is immutable**: Previous repository versions
  that included the package are not affected. Only the new version onward will
  reflect the removal.
- **Auto-publish**: Our repositories are configured to auto-publish on content
  change. A new publication pointing to the new repository version will be
  created automatically after the content modify operation completes.
