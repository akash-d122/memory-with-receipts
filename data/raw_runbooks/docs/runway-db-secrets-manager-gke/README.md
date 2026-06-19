<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Secrets Manager GKE Database (Postgres) Service

* [Service Overview](https://dashboards.gitlab.net/d/runway-db-secrets-manager-gke-main/runway-db-secrets-manager-gke-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22runway-db-secrets-manager-gke%22%2C%20tier%3D%22db%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::RunwayDBSecretsManager"

## Logging

* [runway-db-secrets-manager-gke](https://console.cloud.google.com/logs/query;query=resource.type%3D%22cloudsql_database%22%0Aresource.labels.database_id%3D%22gitlab-runway-production:runway-db-secrets-manager-gke%22%0Alog_name%3D%22projects%2Fgitlab-runway-production%2Flogs%2Fcloudsql.googleapis.com%252Fpostgres.log%22?project=gitlab-runway-production)

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
