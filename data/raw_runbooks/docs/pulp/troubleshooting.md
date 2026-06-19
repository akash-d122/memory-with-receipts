## Troubleshooting Pulp

### Uploaded package not available in repository

1. Ensure that a content has been created for the uploaded package

```bash
pulp deb content list --package=<package-name> --version=<package-version> --architecture=<architecture>
pulp rpm content list --name=<package-name> --version=<package-version> --arch=<architecture>
```

If not, upload the package again, and ensure the task has completed successfully.

1. Get href of the latest version of the repository

```bash
pulp deb repository show --name=<repository-name> | jq -r '.latest_version_href'
pulp rpm repository show --name=<repository-name> | jq -r '.latest_version_href'
```

1. Check if package is in the latest version of the repository

```bash
pulp deb content list --package=<package-name> --version=<package-version> --architecture=<architecture> --repository-version=<repository-version-href>
pulp rpm content list --name=<package-name> --version=<package-version> --arch=<architecture> --repository-version=<repository-version-href>
```

1. If not, add the content to the repository

```bash
pulp deb repository content add --repository=<repository_name> --package-href=<package-content-href>
pulp rpm repository content add --repository=<repository_name> --package-href=<package-content-href>
```

1. Check if a publication exists that points to the latest version of the repository

```bash
pulp deb publication list --repository-version=<latest-repository-version-href>
pulp rpm publication list --repository-version=<latest-repository-version-href>
```

1. If not, create a publication manually

```bash
pulp deb publication create --repository=<repository-name>
pulp rpm publication create --repository=<repository-name>
```

1. Verify that a publication exist with the content

```bash
# Note that `--content` requires a JSON array of hrefs
pulp deb publication list --content='["<package-content-href>"]'
pulp rpm publication list --content='["<package-content-href>"]'
```
