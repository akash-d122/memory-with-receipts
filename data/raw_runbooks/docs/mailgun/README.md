<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Mailgun Service

* [Service Overview](https://dashboards.gitlab.net/d/mailgun-main/mailgun-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22mailgun%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::mailgun"


<!-- END_MARKER -->

<!-- ## Summary -->

<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->
## Alert Details

* **Service ops anomaly detection (volume)**
  Alerts `service_ops_out_of_bounds_upper_5m` and `service_ops_out_of_bounds_lower_5m` fire for `type="mailgun"` when `gitlab_service_ops:rate_5m` deviates significantly (≈3σ) from its 1‑week baseline for 5 minutes. This is our primary protection against unexpected spikes or drops in Mailgun send volume (including potential abuse of resend flows).

* **Mail delivery SLO violation (errors)**
  `MailgunServiceMailDeliveryErrorSLOViolation` alerts when the `mail_delivery` error ratio for Mailgun breaches its SLO over 1‑hour and 6‑hour windows.

* **Mail delivery traffic cessation/absence**
  [`MailgunServiceMailDeliveryTrafficCessation` and `MailgunServiceMailDeliveryTrafficAbsent`](../metrics-catalog/traffic-cessation-alerts.md) alerts fire when Mailgun’s accepted delivery traffic stops, or the underlying metrics disappear, after previously receiving traffic.

## Links to further Documentation

* [Mailgun use at GitLab.com](https://internal.gitlab.com/handbook/engineering/infrastructure/mailgun/)
