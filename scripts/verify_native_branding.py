"""Measure compiled Windows branding; not fingerprint or release admission."""

from __future__ import annotations

import argparse
import asyncio
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native.configuration import NativeConfiguration
from app.core.native.runtime import NativeRuntime
from scripts.native_build import measure_runtime_core
from scripts.verify_native_privacy_units import require_idle_builder


def icon_images(contents: bytes) -> list[dict]:
    if not isinstance(contents, bytes) or not 6 <= len(contents) <= 16 * 1024 * 1024:
        raise ValueError("Invalid bounded Windows icon")
    reserved, kind, count = struct.unpack_from("<HHH", contents)
    if reserved or kind != 1 or not 1 <= count <= 64 or len(contents) < 6 + count * 16:
        raise ValueError("Invalid Windows icon directory")
    result = []
    spans = []
    for index in range(count):
        width, height, colours, reserved, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", contents, 6 + index * 16)
        if reserved or not size or offset < 6 + count * 16 or offset + size > len(contents):
            raise ValueError("Invalid Windows icon image bounds")
        if any(offset < end and start < offset + size for start, end in spans):
            raise ValueError("Overlapping Windows icon images")
        spans.append((offset, offset + size))
        result.append({"width": width, "height": height, "colours": colours, "planes": planes,
                       "bits": bits, "bytes": size,
                       "sha256": hashlib.sha256(contents[offset:offset + size]).hexdigest()})
    return result


def measure_icon_resources(executable: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("Compiled icon checks currently support Windows only")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    kernel.LoadLibraryExW.restype = wintypes.HMODULE
    kernel.FindResourceW.argtypes = [wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p]
    kernel.FindResourceW.restype = wintypes.HANDLE
    kernel.SizeofResource.argtypes = [wintypes.HMODULE, wintypes.HANDLE]
    kernel.SizeofResource.restype = wintypes.DWORD
    kernel.LoadResource.argtypes = [wintypes.HMODULE, wintypes.HANDLE]
    kernel.LoadResource.restype = wintypes.HANDLE
    kernel.LockResource.argtypes = [wintypes.HANDLE]
    kernel.LockResource.restype = ctypes.c_void_p
    kernel.FreeLibrary.argtypes = [wintypes.HMODULE]
    kernel.FreeLibrary.restype = wintypes.BOOL
    module = kernel.LoadLibraryExW(str(executable), None, 0x2 | 0x20)
    if not module:
        raise ctypes.WinError(ctypes.get_last_error())

    def resource(name, kind):
        pointer = ctypes.cast(ctypes.c_wchar_p(name), ctypes.c_void_p) if isinstance(name, str) else ctypes.c_void_p(name)
        entry = kernel.FindResourceW(module, pointer, ctypes.c_void_p(kind))
        if not entry:
            raise ctypes.WinError(ctypes.get_last_error())
        size = kernel.SizeofResource(module, entry)
        loaded = kernel.LoadResource(module, entry)
        data = kernel.LockResource(loaded) if loaded else None
        if not data or not 0 < size <= 16 * 1024 * 1024:
            raise ValueError("Invalid compiled icon resource")
        return ctypes.string_at(data, size)

    result = {}
    try:
        for name in ("IDR_MAINFRAME", "IDR_X001_APP_LIST"):
            group = resource(name, 14)
            if len(group) < 6:
                raise ValueError("Missing compiled icon directory")
            reserved, kind, count = struct.unpack_from("<HHH", group)
            if reserved or kind != 1 or not 1 <= count <= 64 or len(group) != 6 + count * 14:
                raise ValueError("Malformed compiled icon directory")
            images = []
            for index in range(count):
                width, height, colours, reserved, planes, bits, size, identity = struct.unpack_from("<BBBBHHIH", group, 6 + index * 14)
                payload = resource(identity, 3)
                if reserved or len(payload) != size:
                    raise ValueError("Compiled icon payload size mismatch")
                images.append({"width": width, "height": height, "colours": colours, "planes": planes,
                               "bits": bits, "bytes": size, "sha256": hashlib.sha256(payload).hexdigest()})
            result[name] = images
    finally:
        if not kernel.FreeLibrary(module):
            raise ctypes.WinError(ctypes.get_last_error())
    return result


def measure_product_names(executable: Path) -> list[str]:
    if sys.platform != "win32":
        raise ValueError("Compiled version checks currently support Windows only")
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    version.VerQueryValueW.restype = wintypes.BOOL
    ignored = wintypes.DWORD()
    size = version.GetFileVersionInfoSizeW(str(executable), ctypes.byref(ignored))
    if not 0 < size <= 16 * 1024 * 1024:
        raise ValueError("Compiled version information is missing or exceeds its bound")
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(executable), 0, size, buffer):
        raise ctypes.WinError(ctypes.get_last_error())

    def query(key):
        pointer = ctypes.c_void_p()
        count = wintypes.UINT()
        if not version.VerQueryValueW(buffer, key, ctypes.byref(pointer), ctypes.byref(count)) or not pointer:
            raise ValueError("Compiled version field is missing: " + key)
        return pointer, count.value

    translations, count = query("\\VarFileInfo\\Translation")
    if count % 4 or not 4 <= count <= 128:
        raise ValueError("Compiled version translations are invalid")
    names = []
    for language, codepage in struct.iter_unpack("<HH", ctypes.string_at(translations, count)):
        pointer, characters = query(f"\\StringFileInfo\\{language:04x}{codepage:04x}\\ProductName")
        if not 1 < characters <= 4096:
            raise ValueError("Compiled product name has an invalid length")
        text = ctypes.wstring_at(pointer, characters)
        if not text.endswith("\0"):
            raise ValueError("Compiled product name is not terminated")
        names.append(text[:-1])
    return names


def measure_branding_resources(executable: Path) -> dict[str, str]:
    root = executable.parent
    paths = list(root.glob("*.pak")) + list((root / "locales").glob("*.pak"))
    required = {"resources.pak", "chrome_100_percent.pak", "chrome_200_percent.pak", "locales/en-US.pak"}
    if not required.issubset({path.relative_to(root).as_posix() for path in paths}):
        raise ValueError("Compiled branding resource/locale packs are incomplete")
    hashes = {}
    for path in paths:
        if path != path.resolve() or not path.is_file():
            raise ValueError("Compiled branding resource pack is linked or missing")
        with path.open("rb") as stream:
            hashes[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return hashes


async def verify(executable: Path, destination: Path) -> dict:
    if sys.platform != "win32":
        raise ValueError("Native branding verification currently supports Windows only")
    require_idle_builder()
    if executable != executable.resolve() or not executable.is_file():
        raise ValueError("Branding requires a canonical installed executable")
    if (destination != destination.resolve() or destination.exists()
            or destination.is_relative_to(executable.parent) or destination.is_relative_to(ROOT)):
        raise ValueError("Branding requires a fresh evidence directory outside the runtime")
    core = measure_runtime_core(executable)
    receipt_path = executable.parent / "camouflow-build.json"
    if receipt_path != receipt_path.resolve() or not receipt_path.is_file() or receipt_path.stat().st_size > 1024 * 1024:
        raise ValueError("Compiled branding receipt is unsafe or exceeds its bound")
    receipt = receipt_path.read_bytes()
    record = json.loads(receipt.decode("utf-8-sig"))
    patches = [ROOT / "native/patches" / name for name in (
        "0060-native-glint-branding.patch", "0061-native-glint-ui-resources.patch")]
    patch_bytes = {patch.name: patch.read_bytes() for patch in patches}
    logo_path = ROOT / "logo.ico"
    logo_bytes = logo_path.read_bytes()
    expected_patches = [{"name": name, "sha256": hashlib.sha256(contents).hexdigest()}
                        for name, contents in patch_bytes.items()]
    if (record.get("runtime_core_sha256_measured") != core or not isinstance(record.get("patches"), list)
            or any(record["patches"].count(expected) != 1 for expected in expected_patches)):
        raise ValueError("Exact compiled branding receipt required")
    resource_hashes = measure_branding_resources(executable)
    destination.mkdir(parents=True)
    report = {"passed": False, "scope": "Compiled icons/version-page branding only; not visual taskbar/shortcut migration or privacy admission",
              "runtime_core_sha256_measured": core, "checks": [],
              "logo_sha256": hashlib.sha256(logo_bytes).hexdigest(), "branding_patches": expected_patches,
              "resource_pack_sha256": resource_hashes}
    runtime = NativeRuntime(destination / "profile", executable, NativeConfiguration())
    try:
        expected_icons = icon_images(logo_bytes)
        measured_icons = measure_icon_resources(executable)
        report["icons"] = measured_icons
        if any(images != expected_icons for images in measured_icons.values()):
            raise ValueError("Compiled main/app-list icons differ from the project logo")
        report["checks"].append("compiled-main-and-app-list-icons-match-project-logo")
        products = {name: measure_product_names(executable.parent / name) for name in ("chrome.exe", "chrome.dll")}
        report["product_names"] = products
        if any(not names or any(name != "Glint" for name in names) for names in products.values()):
            raise ValueError("Compiled executable/library product names are not Glint")
        report["checks"].append("compiled-executable-and-library-product-names-are-glint")
        context = await runtime.start(headless=True)
        page = await context.new_page()
        await page.goto("chrome://version", wait_until="domcontentloaded", timeout=30000)
        heading = await page.locator("#inner tr:first-child > td.label").inner_text(timeout=10000)
        report["version_page_product"] = heading
        if heading.strip() != "Glint":
            raise ValueError("Version page does not identify the compiled product as Glint")
        report["checks"].append("version-page-product-is-glint")
        report["browser_version"] = context.browser.version
        await page.screenshot(path=str(destination / "version-page.png"))
        report["passed"] = True
    except Exception as error:
        report["error"] = type(error).__name__ + ": " + str(error)
    finally:
        try:
            await runtime.close()
            if runtime.has_resources:
                raise RuntimeError("Branding probe retains resources")
        except Exception as error:
            report["passed"] = False
            report["cleanup_error"] = type(error).__name__ + ": " + str(error)
        try:
            report["inputs_unchanged"] = (core == measure_runtime_core(executable) and receipt == receipt_path.read_bytes()
                                          and all(patch_bytes[patch.name] == patch.read_bytes() for patch in patches)
                                          and logo_bytes == logo_path.read_bytes()
                                          and resource_hashes == measure_branding_resources(executable))
        except (OSError, ValueError) as error:
            report["inputs_unchanged"] = False
            report["input_guard_error"] = type(error).__name__ + ": " + str(error)
        report["passed"] = report["passed"] and report["inputs_unchanged"]
        (destination / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(verify(args.executable, args.output))
    except (ValueError, OSError) as error:
        parser.exit(1, f"Native branding verification failed: {error}\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
