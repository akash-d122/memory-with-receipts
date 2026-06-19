<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Sidekiq Background Jobs Service

* [Service Overview](https://dashboards.gitlab.net/d/sidekiq-main/sidekiq-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22sidekiq%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Sidekiq"

## Logging

* [Sidekiq](https://log.gprd.gitlab.net/goto/d7e4791e63d2a2b192514ac821c9f14f)
* [Rails](https://log.gprd.gitlab.net/goto/86fbcd537588abef69339a352ef81d72)
* [Puma](https://log.gprd.gitlab.net/goto/a2601cff0b6f000339e05cdb9deab58b)
* [Unstructured](https://console.cloud.google.com/logs/viewer?project=gitlab-production&interval=PT1H&resource=gce_instance&advancedFilter=jsonPayload.hostname%3A%22sidekiq%22%0Alabels.tag%3D%22unstructured.production%22&customFacets=labels.%22compute.googleapis.com%2Fresource_name%22)
* [system](https://log.gprd.gitlab.net/goto/72d0f3fdfd8db18db9800cc04d8b6f55)

<!-- END_MARKER -->

<!-- ## Summary -->

<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

<!-- ## Links to further Documentation -->
