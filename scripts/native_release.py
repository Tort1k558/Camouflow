"""Manage explicitly trusted local Native bundles without changing profiles."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.distribution import NativeBinaryStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, type=Path, help="Absolute owned binary store path")
    commands = parser.add_subparsers(dest="action", required=True)
    install = commands.add_parser("install", help="Install a checksum-verified local .tar.gz bundle")
    install.add_argument("--archive", required=True, type=Path)
    install.add_argument("--sha256", required=True, help="Checksum obtained from a trusted publisher")
    install.add_argument("--activate", action="store_true", help="Verify runtime health and activate after installation")
    activate = commands.add_parser("activate", help="Verify and select an installed release")
    activate.add_argument("digest", help="Installed archive SHA-256")
    commands.add_parser("rollback", help="Verify and select the previous compatible release")
    commands.add_parser("current", help="Inspect the active release and verify its executable")
    arguments = parser.parse_args()
    try:
        store = NativeBinaryStore(arguments.store)
        if arguments.action == "install":
            release = store.install_archive(arguments.archive, arguments.sha256)
            if arguments.activate:
                release = asyncio.run(store.activate(release["release_sha256"]))
        elif arguments.action == "activate":
            release = asyncio.run(store.activate(arguments.digest))
        elif arguments.action == "rollback":
            release = asyncio.run(store.rollback())
        else:
            release = store.resolve_active()
    except Exception as error:
        print(f"Native release {arguments.action} failed ({type(error).__name__}): {error}", file=sys.stderr)
        return 1
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
