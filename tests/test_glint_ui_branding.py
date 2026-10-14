from pathlib import Path
import subprocess

import pytest

from scripts import prepare_glint_ui_branding as branding


def test_ui_product_renaming_preserves_ids_attributes_authors_and_os():
    source = ('<message name="IDS_PRODUCT_NAME" desc="Chromium application">Chromium</message>\n'
              '<message name="IDS_NOTICE">The Chromium Authors; ChromiumOS; https://chromium.org</message>\n'
              '<!-- Chromium source comment -->')
    result, count = branding.rename_product_messages(source)
    assert count == 1
    assert 'name="IDS_PRODUCT_NAME" desc="Chromium application">Glint' in result
    assert "The Chromium Authors; ChromiumOS; https://chromium.org" in result
    assert "<!-- Chromium source comment -->" in result


def test_ui_product_renaming_refuses_already_renamed_input():
    with pytest.raises(ValueError, match="No Chromium product messages"):
        branding.rename_product_messages('<message name="IDS_PRODUCT_NAME">Glint</message>')


def test_ui_branding_preparation_roundtrips_assets_without_source_mutation(tmp_path, monkeypatch):
    from PyQt6.QtGui import QImage

    source = tmp_path / "source"
    strings = source / "chrome/app/chromium_strings.grd"
    strings.parent.mkdir(parents=True)
    strings.write_text('<message name="IDS_PRODUCT_NAME">Chromium</message>\n', encoding="utf-8")
    originals = {strings.relative_to(source).as_posix(): strings.read_bytes()}
    for scale in (100, 200):
        for directory, names in (
            (f"chrome/app/theme/default_{scale}_percent/chromium", (
                "product_logo_16.png", "product_logo_32.png", "product_logo_name_22.png", "product_logo_name_22_white.png")),
            (f"components/resources/default_{scale}_percent/chromium", (
                "product_logo.png", "product_logo_white.png", "favicon_product.png")),
        ):
            for name in names:
                path = source / directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                image = QImage(32, 16, QImage.Format.Format_ARGB32)
                image.fill(0xff0000ff)
                assert image.save(str(path), "PNG")
                originals[path.relative_to(source).as_posix()] = path.read_bytes()
    real_run = subprocess.run

    def run(arguments, **kwargs):
        if arguments == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(arguments, 0, branding.LOCK["chromium_revision"] + "\n")
        return real_run(arguments, **kwargs)

    monkeypatch.setattr(branding.subprocess, "run", run)
    patch = tmp_path / "ui-branding.patch"
    report = branding.prepare(source, patch)
    assert report["prepared"] and not report["applied"]
    assert len(report["assets"]) == 15
    assert all((source / name).read_bytes() == data for name, data in originals.items())
    assert b"\r\n" not in patch.read_bytes()
    real_run(["git", "apply", "--check", str(patch)], cwd=source, check=True)
    real_run(["git", "apply", str(patch)], cwd=source, check=True)
    for record in report["assets"]:
        path = source / record["path"]
        if path.suffix == ".png":
            image = QImage(str(path))
            assert (image.width(), image.height()) == (32, 16)
        else:
            assert "Glint" in path.read_text(encoding="utf-8")
    real_run(["git", "apply", "--reverse", str(patch)], cwd=source, check=True)
    assert all((source / name).read_bytes() == data for name, data in originals.items())
