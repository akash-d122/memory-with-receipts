# PGBouncer

## Overview

PGBouncer is a stateless service that acts as a connection pooler for Postgres, with some load balancing built in.

We operate multiple PGBouncer fleets, that handle different portions of the site traffic. As of writing (08/2024), the following fleets exist in production:

- ci
- registry
- sidekiq-ci
- sidekiq
- main

## Lead Time

Clients connect through a GCP network loadbalancer, and connections are sent to active backend nodes. As such we should be able to remove instances from the pool and perform upgrades without significant disruption, or scheduling lead time.

## System Identification

Knife query:

```
knife search node 'roles:gprd-base-db-pgbouncer*' -i | sort
```

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

Upgrades will be performed on individual instances or groups of instances at a time, across the multiple pgbouncer fleets that we run:

- Remove the node from the GCP loadbalancer
- Update packages
- Reboot
- Add the node(s) back to the loadbalancer
- repeat.

## Additional Automation Tooling

None currently exists.
