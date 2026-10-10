# Proxies

The **Proxies** page manages proxy groups, bulk import, health checks and profile assignments.

## Proxy groups

The left panel contains proxy groups:

- **New** creates a group.
- **Rename** renames the selected group.
- **Delete** removes the selected group.
- **All pools** shows proxies from every group.

## Bulk import

Use **Import proxies** and paste proxies one per line.

Supported formats:

```text
ip:port:login:password
scheme://ip:port:login:password
scheme://user:pass@host:port
user:pass@host:port
```

Duplicates are ignored during bulk import.

## Proxy list actions

Each proxy row supports:

- select / unselect
- health-check one proxy
- edit name/value
- delete one proxy

Top actions:

- **Check all proxies** checks every pool, not only the visible group; quarantined
  entries are skipped.
- **Release assignment** clears assignment for selected proxies and removes proxy
  fields from assigned profiles.
- **Remove quarantine** explicitly releases selected quarantined proxies.
- **Delete selected** deletes selected proxies after confirmation.
- **Clear selection** clears selection.

## Statistics

The page shows:

- reachable proxies (successful checks; scope described below)
- unchecked proxies
- checking proxies
- failed proxies
- detected locations

Health checks store latency, status and geo metadata in the proxy pool.

New connections remain **Unchecked** until tested. **Reachable** means the cloud
TCP check reached the host and port; it does not prove proxy authentication,
internet access or exit location. **Active** means the desktop internet probe
succeeded. Neither result guarantees future availability. Location statistics
count detected locations only, not group names.

Proxy lists and dashboard summaries show only the scheme, host and port, without
credentials. The connection value is unchanged; managers can inspect/edit it in
the proxy settings dialog. Treat that dialog and exported configuration as sensitive.

Repeated failures quarantine a connection. Invalid or timezone-ambiguous quarantine
expiry also remains blocked until manual release; the app does not guess a timezone.
Checking one proxy manually can refresh its health while bulk checks skip quarantine.

Results are merged into the current matching proxy, preserving name/assignment,
other proxies and edits made during the check. Removed or changed endpoint results
are discarded. A check never silently restores a deleted proxy.
