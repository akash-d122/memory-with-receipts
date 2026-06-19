# Tutorials

## Purpose

This Tutorials section provides a public area for sharing knowledge with teammates related to operating GitLab at scale.  This helps supports:

* **Onboarding new members of the infrastructure team:**
  This orientation style of tutorial progressively introduces topics along an orderly learning path to establish a broad baseline understanding
  of the major components and their purposes, their interactions and interfaces, their behaviors and ways to observe them.  This general base
  understanding of core concepts, vocabulary, behaviors, and observability establishes a common foundation for efficiently building deeper knowledge
  through more narrowly focused experience, exposure, and training.  This kind of material may also be helpful orientation for other teams at GitLab
  for the same reasons as it helps in onboarding -- establishing a common frame of reference helps facilitate communication between specialists in
  different domains of knowledge.
* **Sharing techniques and tools with teammates:**
  This how-to style of tutorial documents techniques and tools that peers working in the same domain may find helpful.  Typically these tutorials
  will describe a use-case, summarize crucial background knowledge, narrate a concrete demo, and summarize the repeatable steps.  As problem-solving
  tutorials, they aim to explain the rationale behind the method and help interpret outcomes.  Unlike generic tool documentation, these tutorials
  focus on the use-cases and concrete context of our operating environment, so they are more narrowly focused and directly applicable.  As such,
  they also implicitly help introduce elements of that domain-specific knowledge to curious readers.

Sharing reusable techniques through a curated set of overviews and demos helps us rely less on tribal knowledge.
Asynchronous knowledge sharing is especially important in GitLab's globally distributed work model, where colleagues in widely separated time zones
rarely have the chance to informally share tips and insights.

## Suggested guidelines for contributing tutorials

When writing, reviewing, or updating tutorials in this library, consider the optional suggestions in the style guide:

[Tips for writing engaging tutorials that support multiple learning styles](./tips_for_tutorial_writing.md)

For convenience, this template can optionally be used for starting new tutorials:

[Example tutorial template](./example_tutorial_template.md)

## Orientation: Overview of major system components and behaviors

These structured learning tracks progressively introduce aspects of the GitLab.com operating environment.

The goal is to provide a common base understanding of the major system components and their normal behaviors and interactions.

The primary target audience is anyone seeking an overview of how GitLab is run in the GitLab.com environment, including
new and existing team members and the many folks who help us support these systems.

These tutorials tend to be more conceptual than hands-on but still aim to give practical tips for observing the behaviors described.

* [Life of a web request](./overview_life_of_a_web_request.md):
  A high level introduction to the major frontend and backend components of GitLab.com
* [Life of a git request](./overview_life_of_a_git_request.md)  Life of a git request:
  Tracing a git-fetch request through the gitlab.com infrastructure, contrasting git-over-ssh and git-over-http.
* [IN PROGRESS](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10390)  Life of a sidekiq job:
  A high level introduction to asynchronous background job processing, including job creation, scheduling, execution, and callbacks
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10391)  Tour of Postgres HA:
  Walk through the high availability and load balancing mechanisms supporting the main relational database.
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10400)  Tour of Redis at GitLab.com:
  Tour the Redis clusters, their distinct roles as shared caching and queuing datastores, their high availability mechanisms, and scaling constraints.

## How-to: Demos of analytical methods and exploratory tools

These tutorials demonstrate generalizable methods or tools for analyzing interesting system behaviors.  They aim to help with analysis activities with themes like:

* performance bottleneck analysis
* capacity ceiling / scalability constraint discovery
* abuse research
* workload characterization
* attack surface analysis
* resource usage profiling
* dependency tracing
* call graph discovery
* request tracing
* log mining techniques
* ... anything else related to exploring a live subsystem or its artifacts

### Metrics and Monitoring

These tutorials focus on finding, understanding, and using the metrics collected by Prometheus from hosts and services.

Tutorials list:

* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10392)  Intro to GitLab-specific metrics catalogue:
  A quick tour of what metrics are available and how to explore them using basic PromQL filtering and aggregation to answer common questions
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10393)  What does this apdex metric mean?
  Tracing a composite metric back through its recording-rule transformations, down to the original underlying raw metrics exposed by the system component being measured
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10394)  How are metrics collected by Prometheus?
  A tour of the prometheus exporters we use and what sources of information they sample
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10395)  How are metrics exposed by gitlab-rails?
  Learn how to see for yourself: What events increment that counter?  What points in the code start and end this latency measurement?
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10396)  How are metrics exposed by gitlab-workhorse?
  Learn how to see for yourself: What events increment that counter?  What points in the code start and end this latency measurement?
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10397)  How are metrics exposed by gitaly?
  Learn how to see for yourself: What events increment that counter?  What points in the code start and end this latency measurement?
* [TODO](https://gitlab.com/gitlab-com/gl-infra/reliability/-/issues/10398)  How are metrics exposed by gitlab-runners?
  Learn how to see for yourself: What events increment that counter? What points in the code start and end this latency measurement?

### Performance analysis and profiling

These tutorials focus on performance profiling techniques.

Profiling is a broad set of activities generally aiming to learn more about a system's bottlenecks and resource usage under a specific workload.

On horizontally scalable systems like GitLab, when we talk about "profiling" we usually aim to answer latency and throughput questions such as
**"Where was the time spent?"** and **"What was the most constraining resource?"** during whatever event or conditions are under study.
But profiling can also include analyzing other resources such as memory usage, disk and network I/O, lock contention, cache efficiency,
concurrency stalls on a blocked resource, connection pool saturation, etc.

Understanding where a system spends its time, memory, I/O, and other resources helps to focus optimization efforts and capacity planning on the
most relevant areas -- the places in the code or infrastructure that represent a capacity constraint, a tipping point, or a potentially large efficiency gain.

Tutorials list:

* [How to use flamegraphs for performance profiling](./how_to_use_flamegraphs_for_perf_profiling.md):
  Find what code paths we spend the most time in.
* **(TODO)**  Demo: Profiling a process starved for disk I/O, including variants such as synchronous reads, synchronous writes, serial I/O, frequent fsyncs
* **(TODO)**  Demo: Profiling a process starved for network I/O, including bandwidth saturation and latency-bound serial I/O
* **(TODO)**  Demo: Profiling a process starved for connection pool leases
* **(TODO)**  Demo: Profiling a process starved for a lock that serializes threads' access to a critical section of code or a shared data structure
* **(TODO)**  Demo: Profiling a process whose throughput and latency are affected by slower responses during its calls to a service it depends on
