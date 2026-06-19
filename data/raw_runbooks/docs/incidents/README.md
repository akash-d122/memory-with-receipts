# Incidents

General documentation about our incident workflow itself. Service-specific
information, including what to do in response to an incident relating to that
service, is found in the docs for that service.

## Overview

We use [Incident.io](https://app.incident.io/gitlab/dashboard) as the primary automation tool for our incident process.
Most incident information exchange takes place in an incident Slack channel, an incident Zoom meeting, and an Incident.io incident.

### Notifications

Alertmanager, Deadmansnitch, and Pingdom are the sources of alerts from automated systems attempting to detect and inform our on-call of potential incidents.
All three of these sytems will notify Pagerduty, which will then notify the current engineer on call (EoC).

Incident.io can also use Pagerduty to notify the EoC, IMoC, and CMoC that a new high severity incident has been declared.

### Declaring an incident

The Slack command, `/incident`, can be used to declare an incident.
This integration depends on Slack and Incident.io in order to work.

### Mitigations that disable a safety limit

Some incident mitigations work by disabling or relaxing a safety control, for
example:

- turning off a worker concurrency limit
- raising or removing a rate limit
- disabling a feature flag that guards load
- relaxing a circuit breaker, timeout, or other guardrail

These mitigations are frequently the right call in the moment, but they leave the
system running in a degraded safety posture. The risk is that a *temporary*
disable quietly drifts into a *sustained* operating state with no owner and no
deadline — which has directly contributed to follow-on incidents.

Whenever a mitigation disables or relaxes a safety limit, before the incident is
considered resolved it must leave behind a tracked follow-up that satisfies all of
the following:

- **An explicit DRI.** A specific person (not just a group label) is accountable
  for ensuring the limit is re-evaluated and a deliberate decision is made about
  it. This person should be from the team that owns the setting or limit, even if
  they are not the ones with access to action it. This DRI is distinct from the
  incident IC. If it is not clear who the individual DRI should be at the time the
  follow-up is created, default to assigning the manager of the owning team, who is
  then responsible for triaging it to the right person.
- **A re-evaluation deadline.** A concrete date by which the mitigation will be
  revisited (for example, end of next business day, or 24h). The limit was there
  for a reason; the deadline forces a deliberate decision to keep it off, restore
  it, or replace it with a durable fix.
- **A tracked work item that surfaces where humans look.** Open a follow-up issue
  in the [production-engineering tracker](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/new),
  cross-linking the incident. An incident-timeline entry alone is not enough —
  those are forgotten once the channel goes quiet.

To give the follow-up real accountability, label it `~"infradev"` and assign it to
the DRI. The infradev workflow (reinforced through the Operational Excellence
program) is how these get prioritized and prevented from silently slipping. Two
options for setting the deadline:

- Set a specific due date for re-enabling the limit. In this case do **not** set a
  severity, because the triage tooling will overwrite the due date based on
  severity.
- Or set a severity and let the [infradev action SLO](https://handbook.gitlab.com/handbook/product-development/how-we-work/issue-triage/#severity-slos)
  drive the deadline (S1: 1 week, S2: 30 days). This brings accountable action
  even when there is no specific re-enable date.

Examples of this kind of follow-up:

- [Re-enable a disabled worker concurrency limit](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29044)
- [Revisit a rate limit added to mitigate an incident](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28403)

For the rate-limiting-specific case of allowlist bypasses, see also
[Tracking Bypasses](../rate-limiting/README.md#tracking-bypasses).

### Create a Google doc

- Navigate to <https://drive.google.com/>
- Create a new Google Doc
- Click "Share" in the top-right corner
- In the "Get link" section of the modal, click "Change link to GitLab" to make
  the doc shareable with the whole company.
- Change the "Anyone with the link in GitLab" permissions to "Editor"
- Click done.
- Post a link to the doc in Slack
- Good luck!
