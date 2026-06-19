# Onboarding

This is a small curriculum of onboarding sessions and resources for SREs.

There is a foundational synchronous session to set the stage. The rest of the
documents are intended as self-guided explorations with a synchronous follow-up
discussion to clarify questions.

## Fundamentals

- [Reliability team](https://about.gitlab.com/handbook/engineering/infrastructure/team/reliability/)
- [Session: Application architecture](architecture.md)
- [Exploration: Kubernetes at GitLab](gitlab.com_on_k8s.md)
- [Exploration: Diagnosis with Kibana](kibana-diagnosis.md)
- [Incident Diagnosis in a Symptom-based World](../tutorials/diagnosis.md)
- [Apdex alerts](../monitoring/apdex-alerts-guide.md)
- [Incident management](https://about.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/)
- [An impatient SRE's guide to deleting alerts](../monitoring/deleting-alerts.md)

## Tutorials

- [How to use a flamegraph for perf profiling](../tutorials/how_to_use_flamegraphs_for_perf_profiling.md)
- [Life of a web request](../tutorials/overview_life_of_a_web_request.md)
- [Life of a git request](../tutorials/overview_life_of_a_git_request.md)

## Components

### Sidekiq

- [Sidekiq survival guide for SRE](../sidekiq/sidekiq-survival-guide-for-sres.md)
- [Sidekiq developer style guide](https://docs.gitlab.com/ee/development/sidekiq_style_guide.html)

### Redis

- [Redis survival guide for SRE](../redis/redis-survival-guide-for-sres.md)
- [Redis runbook](../redis/redis.md)

### Gitaly

- [Life of a git request](../tutorials/overview_life_of_a_git_request.md)
- [Gitaly HA](https://gitlab.com/gitlab-org/gitaly/blob/master/doc/design_ha.md)
- [Gitaly presentations](https://gitlab.com/gitlab-org/gitaly#presentations)

### Postgres

- [Backups](../patroni/postgresql-backups-wale-walg.md)
