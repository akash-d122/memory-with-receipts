<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Wiz Sensor Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22wiz-runtime-sensor%22%2C%20tier%3D%22inf%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::WizSensor"


<!-- END_MARKER -->

> [!important]
> The main runbook has been migrated to [Internal Handbook](https://internal.gitlab.com/handbook/security/product_security/infrastructure_security/processes/wiz-runtime-sensor). Please refer there for more details.

## Summary

`Wiz Runtime Sensor` is a small ebpf (Extended Berkeley Packet Filter) agent deployed on every Kubernetes Node, meticulously monitoring system calls to pinpoint suspicious activities. It proactively identifies and alerts on behaviours that look malicious, signalling potential security threats or anomalies. The Wiz Sensor operates by leveraging a set of rules that define which system call sequences and activities are deemed abnormal or indicative of security incidents.
