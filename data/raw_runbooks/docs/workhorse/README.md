<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Workhorse Service

* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22workhorse%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Workhorse"

## Logging

* [Workhorse](https://log.gprd.gitlab.net/goto/66979d90ca195652b7a4d10d22ca2db7)

<!-- END_MARKER -->

<!-- ## Summary -->

<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

## Monitoring

* [Workhorse SLI Apdex](https://dashboards.gitlab.net/goto/1RE_jxYNg?orgId=1)
* [Requests by Status Code](https://dashboards.gitlab.net/goto/GE2XjbLNR?orgId=1)
* [p90 Latency Estimate per Route](https://dashboards.gitlab.net/goto/BQ5jCbLNR?orgId=1)
* [p95 Request Duration per Route](https://dashboards.gitlab.net/goto/XHpqCbLHR?orgId=1)
* [Long running (>=10s) requests in Kibana](https://log.gprd.gitlab.net/app/r/s/n9Sfy)

## Alerting

* [WebServiceWorkhorseApdexSLOViolation](https://alerts.gitlab.net/#/alerts?silenced=false&inhibited=false&muted=false&active=true&filter=%7Balertname%3D%22WebServiceWorkhorseApdexSLOViolation%22%7D)
* [WebServiceWorkhorseApdexSLOViolationRegional](https://alerts.gitlab.net/#/alerts?silenced=false&inhibited=false&muted=false&active=true&filter=%7Balertname%3D%22WebServiceWorkhorseApdexSLOViolationRegional%22%7D)

## Playbooks

* [Workhorse Technical Playbook](https://internal.gitlab.com/handbook/engineering/tier2-oncall/playbooks/create/workhorse/)

## Links to further Documentation

* [Git over HTTPS](https://docs.gitlab.com/development/workhorse/handlers/#git-over-https)
