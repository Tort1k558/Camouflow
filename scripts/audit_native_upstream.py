"""Compare the pinned Windows fork with official Stable metadata; never update sources."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Windows&num=20"
MAX_RESPONSE_BYTES = 1024 * 1024


def version_tuple(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("Invalid Chromium version in upstream audit")
    return tuple(int(part) for part in value.split("."))


def compare(lock: dict, releases: list, now: dt.datetime) -> dict:
    pinned = version_tuple(lock.get("chromium_version"))
    revision = lock.get("chromium_revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid pinned Chromium revision")
    if not isinstance(releases, list) or not 1 <= len(releases) <= 20:
        raise ValueError("Official Stable response must contain 1..20 releases")
    if now.tzinfo is None:
        raise ValueError("Upstream audit requires a timezone-aware observation time")
    measured = []
    for release in releases:
        if not isinstance(release, dict) or release.get("channel") != "Stable" or release.get("platform") != "Windows":
            raise ValueError("Official response contains an unexpected channel or platform")
        version_tuple(release.get("version"))
        timestamp = release.get("time")
        commit = release.get("hashes", {}).get("chromium") if isinstance(release.get("hashes"), dict) else None
        if (type(timestamp) is not int or not 0 < timestamp <= now.timestamp() * 1000
                or not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit)):
            raise ValueError("Invalid official release time or Chromium revision")
        measured.append({"version": release["version"], "chromium_revision": commit,
                         "published_utc": dt.datetime.fromtimestamp(timestamp / 1000, dt.timezone.utc).isoformat()})
    latest = max(measured, key=lambda row: version_tuple(row["version"]))
    matches = [row for row in measured if version_tuple(row["version"]) == pinned]
    aligned = pinned == version_tuple(latest["version"]) and any(row["chromium_revision"] == revision for row in matches)
    return {"schema": 1, "observed_utc": now.isoformat(), "source_url": SOURCE_URL,
            "scope": "Official Windows Stable metadata comparison, not a security or release admission",
            "pinned_version": lock["chromium_version"], "pinned_revision": revision,
            "official_releases": measured, "highest_observed_stable": latest,
            "upstream_aligned": aligned,
            "status": "aligned" if aligned else ("behind-stable" if pinned < version_tuple(latest["version"]) else "review-required"),
            "security_review_complete": False, "production_admitted": False,
            "sources_changed": False}


def audit(output: Path) -> dict:
    if (not output.is_absolute() or output != output.resolve() or not output.parent.is_dir()
            or output.is_relative_to(ROOT) or output.exists()):
        raise ValueError("Use a new evidence file in an existing external canonical directory")
    lock_path = ROOT / "native/build-lock.json"
    original = lock_path.read_bytes()
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Glint-upstream-audit"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl() != SOURCE_URL:
            raise ValueError("Unexpected upstream metadata redirect")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Official Stable response exceeded the audit limit")
    report = compare(json.loads(original.decode("utf-8-sig")), json.loads(raw), dt.datetime.now(dt.timezone.utc))
    if lock_path.read_bytes() != original:
        raise ValueError("Pinned build changed during upstream audit")
    report.update(lock_sha256=hashlib.sha256(original).hexdigest(), response_sha256=hashlib.sha256(raw).hexdigest())
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Upstream audit failed: {error}\n")
    print(json.dumps({key: report[key] for key in ("status", "pinned_version", "highest_observed_stable", "production_admitted")}))
    return 0 if report["upstream_aligned"] else 1


if __name__ == "__main__":
    sys.exit(main())
