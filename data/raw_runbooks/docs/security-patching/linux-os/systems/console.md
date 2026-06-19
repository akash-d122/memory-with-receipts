# Console

## Overview

Console instances are used to provide Rails console access to GitLab team members for debugging the rails application using a given environments data.

## Lead Time

Access is generally granted RO as requested by development teams, and as such, rebooting these instances at will should generally be fine. It's important to check with the SRE on call before rebooting the RW machines, as they are occasionally used to validate and perform fixes in production during high severity incidents.

## System Identification

Knife query:

```
knife search node 'roles:gprd-base-console*' -i
```

## Process

See [Linux Patching Overview](../linux-os-patching.md#linux-patching-overview) for generic processes applied to all Linux systems.

- Notify SRE on call that the machines are being rebooted
- Perform package updates
- Reboot the machine

## Additional Automation Tooling

None exists currently
