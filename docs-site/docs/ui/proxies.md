# Proxies

The **Proxies** tab manages proxy pools and assigns proxies to profiles.

## Pools

Pools are listed on the left.

- **New pool** - create a new pool.
- **Rename** - rename the pool.
- **Delete** - delete the pool.

## Pool details

On the right, for the selected pool:

- Proxy list (multi-select supported).
- **Check internet** - check connectivity through proxies (default request to `https://ipwho.is/`).
- **Release selected** - unassign selected proxies from profiles.
- **Remove selected** - remove selected proxies from the pool.

Proxies are assigned during profile import (via *Proxy pool*) and/or in profile settings.

## Bulk import

Paste proxies one per line and click **Append proxies**.

Supported formats:

- `ip:port:login:password`
- `scheme://ip:port:login:password` (scheme: `socks5`, `socks4`, `http`, `https`)
- `user:pass@host:port` is also accepted during checks if present in data.

Duplicates are ignored on import.
