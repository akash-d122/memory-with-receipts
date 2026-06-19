<!-- MARKER: do not edit this section directly. Edit services/service-catalog.yml then run scripts/generate-docs -->

# Websockets Service

* [Service Overview](https://dashboards.gitlab.net/d/websockets-main/websockets3a-overview)
* **Alerts**: <https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22websockets%22%2C%20tier%3D%22sv%22%7D>
* **Label**: gitlab-com/gl-infra/production~"Service::Websockets"


<!-- END_MARKER -->

## Summary

The websockets service is used to handle Action Cable websocket requests to `/-/cable`. This service is mainly used to
deliver real-time updates to the web UI.

Action Cable uses Redis for PUBSUB and does not persist any subscriptions or broadcasted messages.

When a message is delivered to the client, Rails code like permission checks can be executed. So just like any other Rails node,
this service depends on the DB, Gitaly, and all Redis instances.

## GraphQL subscriptions

Issues, merge requests, and other objects use GraphQL subscriptions to update data on the current page in real-time.

When a subscription is triggered, the GraphQL subscription query is executed for each matched subscriber. These executions are
logged in the [Rails logs under the `GraphqlChannel` controller](https://log.gprd.gitlab.net/app/r/s/6td60).

<!-- ## Summary -->

<!-- ## Architecture -->

<!-- ## Performance -->

<!-- ## Scalability -->

<!-- ## Availability -->

<!-- ## Durability -->

<!-- ## Security/Compliance -->

<!-- ## Monitoring/Alerting -->

<!-- ## Links to further Documentation -->
