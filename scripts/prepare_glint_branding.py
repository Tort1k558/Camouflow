"""Prepare Glint branding without modifying the Chromium build checkout."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def prepare(source: Path, output: Path) -> dict:
    if source != source.resolve() or not source.is_dir():
        raise ValueError("Chromium source must be an existing canonical directory")
    if output.exists() or output.is_symlink():
        raise ValueError("Refusing to overwrite a branding patch")
    if output != output.resolve() or output.is_relative_to(source):
        raise ValueError("Branding output must be canonical and outside the Chromium checkout")
    lock = json.loads((ROOT / "native/build-lock.json").read_text(encoding="utf-8-sig"))
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source, check=True,
                              capture_output=True, text=True).stdout.strip()
    if revision != lock["chromium_revision"]:
        raise ValueError("Chromium revision differs from the pinned build lock")
    output.parent.mkdir(parents=True, exist_ok=True)
    svg = (ROOT / "app/qml/theme/brand.svg").read_bytes()
    icon = (ROOT / "logo.ico").read_bytes()
    replacements = {}
    branding_name = "chrome/app/theme/chromium/BRANDING"
    branding = (source / branding_name).read_text(encoding="utf-8-sig")
    for old, new in (("PRODUCT_FULLNAME=Chromium", "PRODUCT_FULLNAME=Glint"),
                     ("PRODUCT_SHORTNAME=Chromium", "PRODUCT_SHORTNAME=Glint"),
                     ("PRODUCT_INSTALLER_FULLNAME=Chromium Installer", "PRODUCT_INSTALLER_FULLNAME=Glint Installer"),
                     ("PRODUCT_INSTALLER_SHORTNAME=Chromium Installer", "PRODUCT_INSTALLER_SHORTNAME=Glint Installer")):
        if branding.count(old) != 1:
            raise ValueError("Unexpected upstream branding")
        branding = branding.replace(old, new)
    replacements[branding_name] = branding.encode("utf-8")
    shortcut_name = "chrome/browser/profiles/profile_shortcut_manager_win.cc"
    shortcut = (source / shortcut_name).read_text(encoding="utf-8-sig")
    old_version = "const int kCurrentProfileIconVersion = 10;"
    if shortcut.count(old_version) != 1:
        raise ValueError("Unexpected Windows profile icon version")
    replacements[shortcut_name] = shortcut.replace(
        old_version, "const int kCurrentProfileIconVersion = 11;").encode("utf-8")
    replacements["chrome/app/theme/chromium/win/chromium.ico"] = icon
    replacements["chrome/app/theme/chromium/win/app_list.ico"] = icon
    replacements["chrome/app/theme/chromium/product_logo.svg"] = svg

    # Rasterize the existing vector logo; do not redraw or generate a new mark.
    from PyQt6.QtCore import QByteArray, QRectF
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg))
    if not renderer.isValid():
        raise ValueError("The existing CamouFlow vector logo is invalid")
    records = []
    patch = ""
    with tempfile.TemporaryDirectory(prefix="glint-branding-", dir=output.parent) as owned:
        temporary = Path(owned)
        for size in (16, 24, 48, 64, 128, 256):
            image = QImage(size, size, QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = QPainter(image)
            renderer.render(painter, QRectF(0, 0, size, size))
            painter.end()
            png = temporary / f"logo-{size}.png"
            if not image.save(str(png), "PNG"):
                raise OSError("Unable to encode the existing logo")
            replacements[f"chrome/app/theme/chromium/product_logo_{size}.png"] = png.read_bytes()
        for index, (name, contents) in enumerate(replacements.items()):
            original = (source / name).read_bytes()
            if contents == original:
                raise ValueError(f"Branding is already applied: {name}")
            if name.endswith(("BRANDING", ".cc", ".svg")):
                before = original.decode("utf-8-sig")
                after = contents.decode("utf-8")
                if not after.endswith("\n"):
                    after += "\n"
                    contents = after.encode("utf-8")
                lines = difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                            fromfile="a/" + name, tofile="b/" + name)
                patch += f"diff --git a/{name} b/{name}\n" + "".join(
                    line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
                    for line in lines)
            else:
                target = temporary / f"asset-{index}"
                target.write_bytes(contents)
                result = subprocess.run(["git", "diff", "--no-index", "--binary", "--", str(source / name), str(target)],
                                        capture_output=True, text=True)
                if result.returncode != 1 or "GIT binary patch" not in result.stdout:
                    raise RuntimeError("Git did not produce the expected binary asset patch")
                patch += f"diff --git a/{name} b/{name}\n" + result.stdout.split("\n", 1)[1]
            records.append({"path": name, "before_sha256": hashlib.sha256(original).hexdigest(),
                            "after_sha256": hashlib.sha256(contents).hexdigest()})
    output.write_text(patch, encoding="utf-8", newline="\n")
    return {"product_name": "Glint", "source_revision": revision,
            "patch": str(output), "patch_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "assets": records, "applied": False,
            "scope": "Prepared Windows/product branding only; no executable, UA or runtime contract renaming"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        if args.report is not None:
            if args.report.exists() or args.report.is_symlink() or args.report.resolve() == args.output.resolve():
                raise ValueError("Refusing to overwrite a branding report or patch")
            if args.report != args.report.resolve() or args.report.is_relative_to(args.source):
                raise ValueError("Branding report must be canonical and outside the Chromium checkout")
        report = prepare(args.source, args.output)
        if args.report is not None:
            args.report.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as error:
        parser.exit(1, f"Glint branding preparation failed: {error}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
