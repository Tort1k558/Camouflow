"""Explicit pre-launch proxy policies. Never rotate a running browser's IP."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from app.services.proxy_health import probe_proxy_endpoint


def account_proxy(account: dict) -> str:
    host, port = account.get("proxy_host"), account.get("proxy_port")
    if not host or not port:
        return ""
    host = f"[{host}]" if ":" in str(host) and not str(host).startswith("[") else host
    user = quote(str(account.get("proxy_user") or ""), safe="")
    password = quote(str(account.get("proxy_password") or ""), safe="")
    auth = f"{user}:{password}@" if user else ""
    return f"{account.get('proxy_scheme') or 'socks5'}://{auth}{host}:{port}"


def choose_proxy(account: dict, policy: str, candidates: list[dict], cancel, probe=probe_proxy_endpoint) -> str:
    current = account_proxy(account)
    if policy == "unchanged":
        return current
    if policy not in {"check", "replace_failed"}:
        raise ValueError("Unknown proxy policy")
    if current and not cancel.is_set() and probe(current, timeout_s=5.0)[0]:
        return current
    if policy == "check":
        raise ValueError("Assigned proxy is missing or failed its pre-launch check. No direct connection was attempted.")
    for entry in candidates:
        if cancel.is_set():
            raise ValueError("Proxy check canceled")
        if entry.get("assigned_to") not in {None, "", account.get("name"), account.get("id")}:
            continue
        until = entry.get("quarantine_until")
        if until:
            expiry = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry > datetime.now(timezone.utc):
                continue
        value = str(entry.get("value") or "")
        if not value or value == current or entry.get("status") == "quarantined":
            continue
        if probe(value, timeout_s=5.0)[0]:
            return value
    raise ValueError("No healthy, available proxy in the selected pool. Launch stopped.")
