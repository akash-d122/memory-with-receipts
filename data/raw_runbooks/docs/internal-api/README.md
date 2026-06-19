<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# GitLab Internal API Service

* [Service Overview](https://dashboards.gitlab.net/d/internal-api-main/internal-api-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22internal-api%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Internal-API"

## Logging

* [Rails](https://log.gprd.gitlab.net/goto/82dff8e0-a6d3-11ed-9f43-e3784d7fe3ca)
* [Workhorse](https://log.gprd.gitlab.net/goto/624babb0-a6d3-11ed-9f43-e3784d7fe3ca)
* [Kubernetes](https://log.gprd.gitlab.net/goto/ecea3b70-a6d2-11ed-85ed-e7557b0a598c)

<!-- END_MARKER -->

## Summary

Internal API service is used to avoid sending internal traffic to a public loadbalancer. Services like Gitlab Shell and KAS are using `internal-api` to authorise git requests and recieving agent data. More information can be found on [internal endpoint](https://docs.gitlab.com/ee/development/internal_api/#internal-api) documentation.
<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

<!-- ## Links to further Documentation -->
