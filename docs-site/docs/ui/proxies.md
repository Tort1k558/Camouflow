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

Search the cached inventory by name, visible address, group, type or detected
location and combine it with a status filter. Search is case-insensitive and does
not send requests on each keystroke or search stored credentials. Reset restores
the list. Changing filters clears selection to avoid hidden destructive targets.
Statistics describe the selected group before search/status filtering;
**Check all proxies** still checks all pools.

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

The desktop probe supports HTTP and SOCKS proxies, including authenticated
HTTP CONNECT to HTTPS sites. A proxy whose own connection requires TLS
(`https://proxy…`) is not probed: it returns an explicit unsupported error, never
a plaintext downgrade. Use the actual scheme supplied by your proxy provider.
URL-encoded credentials are decoded for authentication; IPv6 hosts stay bracketed
in browser configuration. Invalid ports/formats block browser launch rather than
starting a direct connection.

The internet probe requires a successful geo response with a valid exit IP.
Empty/list JSON, missing/invalid IP, negative success flags and redirects do not
make a proxy Active.

Geo lookups use a per-profile connection, never process-wide SOCKS settings.
Environment proxy/bypass settings cannot route a configured profile's lookup
directly. SOCKS DNS stays at the proxy; IPv6 upstreams are supported by the health
probe and local adapter. TLS-to-proxy geo/health checks are unsupported and fail
closed; HTTPS sites through HTTP CONNECT or SOCKS still use certificate and
hostname verification.

Proxy lists and dashboard summaries show only the scheme, host and port, without
credentials. The connection value is unchanged; managers can inspect/edit it in
the proxy settings dialog. Treat that dialog and exported configuration as sensitive.

Repeated failures quarantine a connection. Invalid or timezone-ambiguous quarantine
expiry also remains blocked until manual release; the app does not guess a timezone.
Checking one proxy manually can refresh its health while bulk checks skip quarantine.

Results are merged into the current matching proxy, preserving name/assignment,
other proxies and edits made during the check. Removed or changed endpoint results
are discarded. A check never silently restores a deleted proxy.

Cloud row actions target the ID shown in the current list, not a newly loaded
position. If a refresh changes inventory order or membership, bulk selection is
cleared. Edit/delete dialogs retain the original cloud ID; a workspace change
requires reopening the dialog.
