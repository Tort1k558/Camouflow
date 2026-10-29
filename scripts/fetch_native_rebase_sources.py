"""Fetch only manifest-pinned Gitiles inputs; no checkout, build, retries or activation."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_native_rebase_draft import checked_child, checked_relative_path, load_manifest

MAX_FILE_BYTES = 16 * 1024**2
MAX_TOTAL_BYTES = 64 * 1024**2
MAX_FILES = 1000
MIN_REQUEST_INTERVAL_SECONDS = 2.0
REPORT_NAME = "source-fetch-report.json"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def source_plan(manifest: dict) -> list[dict]:
    rows = manifest["source_files"]
    if len(rows) > MAX_FILES:
        raise ValueError("Too many sparse source files")
    seen, total = set(), 0
    dependencies = manifest.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise ValueError("Invalid draft dependency map")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid sparse source entry")
        name = row.get("path")
        relative = checked_relative_path(name)
        if (relative.as_posix() != name or name.casefold() in seen or name.casefold() == REPORT_NAME
                or any(part.casefold() == ".git" or any(ord(char) < 32 for char in part) for part in relative.parts)):
            raise ValueError("Duplicate or unsafe sparse source path")
        seen.add(name.casefold())
        if (type(row.get("bytes")) is not int or not 0 <= row["bytes"] <= MAX_FILE_BYTES
                or not isinstance(row.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("Sparse sources require bounded byte lengths and SHA-256 values")
        total += row["bytes"]
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Sparse source byte budget exceeded")
        revision, repository, upstream_name = manifest["target_revision"], "chromium/src", name
        if name.startswith("v8/"):
            v8 = dependencies.get("v8")
            if (not isinstance(v8, dict) or not isinstance(v8.get("revision"), str)
                    or not re.fullmatch(r"[0-9a-f]{40}", v8["revision"])
                    or v8.get("repository") != "https://chromium.googlesource.com/v8/v8.git"):
                raise ValueError("V8 source URLs require the pinned dependency")
            revision, repository, upstream_name = v8["revision"], "v8/v8", name[3:]
        expected = ("https://chromium.googlesource.com/" + repository + "/+/" + revision + "/"
                    + urllib.parse.quote(upstream_name, safe="/") + "?format=TEXT")
        if row.get("url") != expected:
            raise ValueError("Source URL does not match its immutable official revision and path")
    return rows


def validate_content(content: bytes, row: dict) -> bytes:
    if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
        raise ValueError("Source size/checksum mismatch: " + row["path"])
    return content


def read_source(root: Path, row: dict) -> bytes:
    path = checked_child(root, row["path"])
    with path.open("rb") as stream:
        return validate_content(stream.read(row["bytes"] + 1), row)


def fetch_sources(manifest_path: Path, output: Path, *, cache: Path | None = None) -> dict:
    raw, manifest = load_manifest(manifest_path)
    rows = source_plan(manifest)
    if (not output.is_absolute() or output != output.resolve() or output.exists()
            or not output.parent.is_dir() or output.is_relative_to(ROOT)):
        raise ValueError("Use a fresh external canonical source directory")
    if cache is not None and (not cache.is_absolute() or cache != cache.resolve()
            or not cache.is_dir() or output.is_relative_to(cache)):
        raise ValueError("Use an existing canonical read-only cache outside the output")
    cached = {}
    if cache is not None:
        for row in rows:
            path = cache.joinpath(*checked_relative_path(row["path"]).parts)
            if path.exists() or path.is_symlink() or path.is_junction():
                cached[row["path"]] = read_source(cache, row)
    output.mkdir()
    report = {"schema": 1, "passed": False, "compiled": False, "runtime_verified": False,
              "production_admitted": False, "scope": "Checksummed sparse source retrieval only",
              "manifest_sha256": hashlib.sha256(raw).hexdigest(), "target_revision": manifest["target_revision"],
              "target_version": manifest.get("target_version"), "files": [], "network_requests": 0,
              "cache_hits": 0, "minimum_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS}

    def save():
        (output / REPORT_NAME).write_text(json.dumps(report, indent=2), encoding="utf-8")

    save()
    last_request = None
    opener = None
    try:
        for row in rows:
            if row["path"] in cached:
                content, origin = cached[row["path"]], "cache"
                report["cache_hits"] += 1
            else:
                if last_request is not None:
                    delay = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - last_request)
                    if delay > 0:
                        time.sleep(delay)
                last_request = time.monotonic()
                report["network_requests"] += 1
                request = urllib.request.Request(row["url"], headers={"User-Agent": "Glint-pinned-source-fetch"})
                if opener is None:
                    opener = urllib.request.build_opener(NoRedirect())
                with opener.open(request, timeout=30) as response:
                    if response.geturl() != row["url"]:
                        raise ValueError("Unexpected immutable source redirect")
                    encoded_limit = 4 * ((row["bytes"] + 2) // 3)
                    encoded = response.read(encoded_limit + 1)
                    if len(encoded) > encoded_limit:
                        raise ValueError("Encoded source exceeds its declared size")
                    content = validate_content(base64.b64decode(encoded, validate=True), row)
                origin = "https"
            path = output.joinpath(*checked_relative_path(row["path"]).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path != path.resolve():
                raise ValueError("Source output path became linked")
            with path.open("xb") as stream:
                if stream.write(content) != len(content):
                    raise OSError("Incomplete sparse source write")
            report["files"].append({"path": row["path"], "sha256": row["sha256"],
                                    "bytes": len(content), "origin": origin})
            save()
        if load_manifest(manifest_path)[0] != raw:
            raise ValueError("Manifest changed during sparse source retrieval")
        for row in rows:
            read_source(output, row)
            if row["path"] in cached:
                read_source(cache, row)
        report.update(passed=True, manifest_unchanged=True, output_verified=True,
                      cache_verified=True if cached else None)
    except (OSError, ValueError) as error:
        report.update(error_type=type(error).__name__, error=str(error)[:1000])
        if isinstance(error, urllib.error.HTTPError):
            report.update(http_status=error.code, failed_url=error.url,
                          retry_after=(error.headers.get("Retry-After") or "")[:128])
            error.close()
    finally:
        save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache", type=Path, help="Read-only prior source directory; invalid cached bytes abort before HTTP")
    args = parser.parse_args()
    try:
        report = fetch_sources(args.manifest, args.output, cache=args.cache)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Sparse source preparation refused: {error}\n")
    print(json.dumps({key: value for key, value in report.items() if key != "files"}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
