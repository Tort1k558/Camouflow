"""Stable identity for a frozen scenario definition."""

import hashlib
import json


def definition_hash(steps):
    return hashlib.sha256(
        json.dumps(steps, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
