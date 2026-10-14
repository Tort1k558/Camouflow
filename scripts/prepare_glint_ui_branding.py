"""Prepare Glint UI strings/scaled logos without mutating Chromium sources."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.native_build import LOCK


def rename_product_messages(text: str) -> tuple[str, int]:
    changes = 0

    def replace(message):
        nonlocal changes
        body, count = re.subn(r"\bChromium\b(?!\s+Authors)", "Glint", message[2])
        changes += count
        return message[1] + body + message[3]

    result = re.sub(r"(<message\b[^>]*>)(.*?)(</message>)", replace, text, flags=re.S)
    if not changes:
        raise ValueError("No Chromium product messages found for the UI branding patch")
    return result, changes


def prepare(source: Path, output: Path) -> dict:
    if source != source.resolve() or not source.is_dir():
        raise ValueError("UI branding requires canonical Chromium sources")
    if output != output.resolve() or output.exists() or output.is_relative_to(source):
        raise ValueError("UI branding requires a fresh output outside Chromium sources")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source,
                              check=True, capture_output=True, text=True).stdout.strip()
    if revision != LOCK["chromium_revision"]:
        raise ValueError("UI branding requires the pinned Chromium revision")
    from PyQt6.QtCore import QByteArray, QRectF, Qt
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    icon = (ROOT / "app/qml/theme/brand.svg").read_bytes()
    wordmark = (ROOT / "native/branding/glint-wordmark.svg").read_bytes()
    white = wordmark.replace(b'id="glint-wordmark-name" fill="#202820"',
                             b'id="glint-wordmark-name" fill="#edf3e8"')
    if white == wordmark or b"<text" in wordmark:
        raise ValueError("Pinned outline wordmark with a distinct light variant is required")
    renderers = {"icon": QSvgRenderer(QByteArray(icon)), "name": QSvgRenderer(QByteArray(wordmark)),
                 "white": QSvgRenderer(QByteArray(white))}
    if any(not renderer.isValid() for renderer in renderers.values()):
        raise ValueError("Project branding vector is invalid")
    for renderer in renderers.values():
        renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
    strings_name = "chrome/app/chromium_strings.grd"
    original_strings = (source / strings_name).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    renamed, count = rename_product_messages(original_strings)
    replacements = {strings_name: renamed.encode("utf-8")}
    asset_kinds = {}
    for scale in (100, 200):
        chrome = f"chrome/app/theme/default_{scale}_percent/chromium/"
        component = f"components/resources/default_{scale}_percent/chromium/"
        asset_kinds.update({chrome + "product_logo_16.png": "icon", chrome + "product_logo_32.png": "icon",
                           chrome + "product_logo_name_22.png": "name", chrome + "product_logo_name_22_white.png": "white",
                           component + "product_logo.png": "name", component + "product_logo_white.png": "white",
                           component + "favicon_product.png": "icon"})
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    patch = ""
    with tempfile.TemporaryDirectory(prefix="glint-ui-branding-", dir=output.parent) as owned:
        temporary = Path(owned)
        for index, (name, kind) in enumerate(asset_kinds.items()):
            original = source / name
            if original != original.resolve() or not original.is_file():
                raise ValueError("Scaled branding asset is missing or linked")
            dimensions = QImage(str(original))
            if dimensions.isNull() or not 1 <= dimensions.width() <= 1024 or not 1 <= dimensions.height() <= 1024:
                raise ValueError("Scaled branding asset dimensions are invalid")
            image = QImage(dimensions.width(), dimensions.height(), QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = QPainter(image)
            renderers[kind].render(painter, QRectF(0, 0, image.width(), image.height()))
            painter.end()
            target = temporary / f"logo-{index}.png"
            if not image.save(str(target), "PNG"):
                raise OSError("Unable to encode scaled branding asset")
            replacements[name] = target.read_bytes()
        for index, (name, contents) in enumerate(replacements.items()):
            original = (source / name).read_bytes()
            if contents == original:
                raise ValueError("UI branding asset is already applied: " + name)
            if name.endswith(".grd"):
                lines = difflib.unified_diff(original_strings.splitlines(True), contents.decode("utf-8").splitlines(True),
                                            fromfile="a/" + name, tofile="b/" + name)
                patch += f"diff --git a/{name} b/{name}\n" + "".join(lines)
            else:
                target = temporary / f"asset-{index}"
                target.write_bytes(contents)
                result = subprocess.run(["git", "diff", "--no-index", "--binary", "--", str(source / name), str(target)],
                                        capture_output=True, text=True)
                if result.returncode != 1 or "GIT binary patch" not in result.stdout:
                    raise ValueError("Unable to generate scaled branding binary patch")
                patch += f"diff --git a/{name} b/{name}\n" + result.stdout.split("\n", 1)[1]
            records.append({"path": name, "before_sha256": hashlib.sha256(original).hexdigest(),
                            "after_sha256": hashlib.sha256(contents).hexdigest()})
    output.write_text(patch, encoding="utf-8", newline="\n")
    return {"prepared": True, "applied": False, "source_revision": revision,
            "patch_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "renamed_product_mentions": count,
            "assets": records, "scope": "UI resource preparation only; compiled branding still requires verification"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare(args.source, args.output)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Glint UI branding failed: {error}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
