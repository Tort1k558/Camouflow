from pathlib import Path
import asyncio
import hashlib
import json
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.verify_native_branding import icon_images
from scripts import verify_native_branding as branding


def icon(payload=b"owned-icon", offset=22, size=None):
    return (struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 16, 16, 0, 0, 1, 32,
            len(payload) if size is None else size, offset) + payload)


def test_icon_parser_measures_the_actual_payload():
    import hashlib
    rows = icon_images(icon())
    assert rows == [{"width": 16, "height": 16, "colours": 0, "planes": 1,
                     "bits": 32, "bytes": 10, "sha256": hashlib.sha256(b"owned-icon").hexdigest()}]


def test_project_logo_is_a_valid_icon_input():
    rows = icon_images((Path(__file__).resolve().parents[1] / "logo.ico").read_bytes())
    assert rows and all(len(row["sha256"]) == 64 for row in rows)


@pytest.mark.parametrize("data", [b"", b"bad", struct.pack("<HHH", 0, 2, 1),
                                 struct.pack("<HHH", 0, 1, 0), icon(offset=0), icon(size=100),
                                 icon(size=0), bytearray(icon())])
def test_invalid_icon_bounds_or_types_reject(data):
    with pytest.raises(ValueError):
        icon_images(data)


def test_overlapping_icon_images_reject():
    header = struct.pack("<HHH", 0, 1, 2)
    entry = struct.pack("<BBBBHHII", 16, 16, 0, 0, 1, 32, 10, 38)
    with pytest.raises(ValueError, match="Overlapping"):
        icon_images(header + entry + entry + b"owned-icon")


@pytest.mark.parametrize("problem", [None, "wrong-icons", "wrong-product", "wrong-page", "cleanup", "core-changed",
                                     "resources-changed", "resource-removed"])
def test_compiled_branding_workflow_fails_closed(tmp_path, monkeypatch, problem):
    public = tmp_path / "public"
    patch = public / "native/patches/0060-native-glint-branding.patch"
    patch.parent.mkdir(parents=True)
    patch.write_bytes(b"owned-branding-patch")
    ui_patch = patch.with_name("0061-native-glint-ui-resources.patch")
    ui_patch.write_bytes(b"owned-ui-branding-patch")
    (public / "logo.ico").write_bytes(icon())
    installed = tmp_path / "runtime"
    installed.mkdir()
    executable = installed / "chrome.exe"
    executable.write_bytes(b"owned-executable")
    for name in ("resources.pak", "chrome_100_percent.pak", "chrome_200_percent.pak", "locales/en-US.pak"):
        path = installed / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned-resource-pack")
    core = {"chrome.exe": "a" * 64, "chrome.dll": "b" * 64, "chrome_elf.dll": "c" * 64}
    (installed / "camouflow-build.json").write_text(json.dumps({
        "runtime_core_sha256_measured": core,
        "patches": [{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in (patch, ui_patch)],
    }), encoding="utf-8")
    monkeypatch.setattr(branding, "ROOT", public)
    monkeypatch.setattr(branding.sys, "platform", "win32")
    monkeypatch.setattr(branding, "require_idle_builder", lambda *args: None)
    calls = []

    def measured_core(_):
        calls.append(True)
        return {**core, "chrome.dll": "d" * 64} if problem == "core-changed" and len(calls) > 1 else core

    monkeypatch.setattr(branding, "measure_runtime_core", measured_core)
    images = icon_images(icon(b"other-icon") if problem == "wrong-icons" else icon())
    monkeypatch.setattr(branding, "measure_icon_resources", lambda _: {"IDR_MAINFRAME": images, "IDR_X001_APP_LIST": images})
    monkeypatch.setattr(branding, "measure_product_names", lambda _: ["Chromium" if problem == "wrong-product" else "Glint"])
    page = SimpleNamespace(goto=AsyncMock(), screenshot=AsyncMock(),
                           locator=lambda selector: SimpleNamespace(inner_text=AsyncMock(
                               return_value="Chromium" if problem == "wrong-page" else "Glint")))
    context = SimpleNamespace(new_page=AsyncMock(return_value=page), browser=SimpleNamespace(version="148.0.7778.96"))
    runtime = SimpleNamespace(start=AsyncMock(return_value=context), has_resources=True)

    async def close():
        if problem == "cleanup":
            raise RuntimeError("Owned cleanup failure")
        if problem == "resources-changed":
            (installed / "resources.pak").write_bytes(b"changed-resource-pack")
        if problem == "resource-removed":
            (installed / "resources.pak").unlink()
        runtime.has_resources = False

    runtime.close = close
    monkeypatch.setattr(branding, "NativeRuntime", lambda *_: runtime)
    result = asyncio.run(branding.verify(executable, tmp_path / "evidence"))
    assert result["passed"] is (problem is None)
    assert (tmp_path / "evidence/report.json").is_file()
    if problem in {"wrong-icons", "wrong-product"}:
        runtime.start.assert_not_called()
    if problem == "cleanup":
        assert result["cleanup_error"]
    if problem in {"core-changed", "resources-changed", "resource-removed"}:
        assert result["inputs_unchanged"] is False
    if problem is None:
        assert len(result["checks"]) == 3
        assert result["inputs_unchanged"] is True
        assert "not visual taskbar" in result["scope"]
