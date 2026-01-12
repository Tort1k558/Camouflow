"""Parsing helpers for accounts and proxies."""

from __future__ import annotations

import re
from typing import Dict, Tuple


DEFAULT_ACCOUNT_TEMPLATE = "{email};{password};{secret_key};{extra};{twofa_url}"


def parse_account_line(line: str, template: str = DEFAULT_ACCOUNT_TEMPLATE) -> Dict[str, str]:
    line = line.strip()
    if not line:
        raise ValueError("Empty account line")
    template = template.strip() or DEFAULT_ACCOUNT_TEMPLATE

    placeholders = re.findall(r"{([^}]+)}", template)
    if not placeholders:
        raise ValueError("Template must contain placeholders like {email}")
    # derive delimiter from template (first non-empty separator between placeholders)
    parts = re.split(r"{[^}]+}", template)
    delim = ";"
    for part in parts:
        if part:
            delim = part
            break
    values = [p.strip() for p in line.split(delim)]
    if len(values) != len(placeholders):
        raise ValueError(f"Expected {len(placeholders)} fields, got {len(values)} with delimiter '{delim}'")
    data = dict(zip(placeholders, values))
    return {k: str(v) for k, v in data.items()}


def parse_proxy_line(line: str) -> Tuple[str, int, str, str]:
    raw = line.strip()
    if "://" in raw:
        _, raw = raw.split("://", 1)
    parts = [p.strip() for p in raw.split(":")]
    if len(parts) != 4:
        raise ValueError("Proxy line must be ip:port:login:password")
    host, port_str, user, password = parts
    try:
        port = int(port_str)
    except ValueError:
        raise ValueError("Proxy port must be a number")
    return host, port, user, password

