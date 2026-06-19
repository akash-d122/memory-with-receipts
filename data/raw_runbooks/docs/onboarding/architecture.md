# Session: Application architecture

This is a synchronous session that covers the foundational architecture of
GitLab.com.

## Agenda

- [Architecture diagram](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/production/architecture/)
- GCP console overview of VMs
- Life of a request: web ([tutorial](../tutorials/overview_life_of_a_web_request.md))
  - `Cloudflare` => `HAProxy` (routing to webservice api/git/web) => `web: Workhorse` => `web: rails` => Databases (Postgres, Redis, `Gitaly`, GCS)
- Life of a request: git ([tutorial](../tutorials/overview_life_of_a_git_request.md))
  - https: `Cloudflare` => `HAProxy` => `git: Workhorse` (=> `git: rails` for authn) => `Gitaly`
  - ssh: `Cloudflare` => `HAProxy` => `gitlab-shell` (=> `git: rails` for authn) => `Gitaly`
- Exploration of hosts over SSH
  - Looking at running processes, discovering service configuration

## Resources

- Architecture diagrams
  - Production GitLab.com environment diagrams: <https://about.gitlab.com/handbook/engineering/infrastructure-platforms/production/architecture/>
  - Application component list with descriptions and links: <https://docs.gitlab.com/ce/development/architecture.html#components>
  - Recorded session presented by Andrew Newdigate at Jan 2021: <https://www.youtube.com/watch?v=P3NhrEoSkeI>
    - this video is private, hence use the Unfiltered Youtube account -
<https://about.gitlab.com/handbook/marketing/marketing-operations/youtube/#unable-to-view-a-video-on-youtube>

- Chef
  - GitLab-specific: Laptop setup, cookbook change workflow, secrets management, one-liners: <https://ops.gitlab.net/gitlab-cookbooks/chef-repo#getting-started>
  - Generic Chef documentation:
    - Chef Overview (use this as a glossary of Chef vocabulary): <https://docs.chef.io/chef_overview/>
    - Chef Resource reference (list of built-in resource objects, e.g. `file`, `apt_package`): <https://docs.chef.io/resources/>
    - Chef Node Attributes (data for use in recipes, provided to chef-client about the current node's present or desired state): <https://docs.chef.io/attributes/>
- Terraform
  - Note: We are using Terraform version 0.12.x in all GitLab's environments.  The TF docs often mention 0.12 as a major version boundary, and you can ignore caveats about behavior differences older TF versions.
  - GitLab-specific: How to use terraform for managing GitLab.com resources: <https://ops.gitlab.net/gitlab-com/gitlab-com-infrastructure/-/blob/master/README.md>
  - Video demo of creating staging environment: <https://drive.google.com/open?id=0BzamLYNnSQa_cjN5NGtaRnpyRXc>
  - Generic Terraform documentation:
    - Terraform CLI and config language docs: <https://www.terraform.io/docs/cli-index.html>
    - Terraform Glossary: <https://www.terraform.io/docs/glossary.html>
    - GCP-specific Terraform Provider: <https://www.terraform.io/docs/providers/google/guides/provider_reference.html>
- Runbooks for GitLab.com: <https://gitlab.com/gitlab-com/runbooks/-/tree/master/>
  - This git repo contains much more than just "runbooks".
  - It is the main place where we collect internal documentation and advice to ourselves for working with our infrastructure components and services.
  - `/docs` sub-directory contain more up-to-date Runbooks than the root directory in this Repo.
  - It also composes metrics, alerts, and dashboards for our services using jsonnet.
  - We should probably record a guided tour of this repo.  Or just commit to giving a tour in a pairing session.
