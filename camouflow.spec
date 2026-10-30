# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH).resolve()

datas = [
    (str(ROOT / "logo.ico"), "."),
    (str(ROOT / "scenaries"), "scenaries"),
    (str(ROOT / "app" / "qml"), "app/qml"),
    (str(ROOT / "app" / "services" / "ai_agent" / "dom.js"), "app/services/ai_agent"),
]

# Windows Explorer / SmartScreen metadata for CamouFlow.exe.
APP_VERSION_INFO = str(ROOT / "version_info.txt")

datas += collect_data_files("browserforge")
datas += collect_data_files("apify_fingerprint_datapoints")
hiddenimports = collect_submodules("browserforge")
hiddenimports += [
    "csv",
    "math",
    "datetime",
    "pathlib",
    "asyncio",
    "PyQt6.QtQml",
    "PyQt6.QtQuick",
    "playwright.__main__",
]

# camoufox ships non-.py assets (e.g. YAML manifests) that must be bundled.
datas += collect_data_files("camoufox")
hiddenimports += collect_submodules("camoufox")

# CloakBrowser ships helper modules and metadata for its Chromium downloader.
datas += collect_data_files("cloakbrowser")
hiddenimports += collect_submodules("cloakbrowser")

# language_tags ships JSON indexes under language_tags/data/json.
datas += collect_data_files("language_tags")
hiddenimports += collect_submodules("language_tags")

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

driver_stage = os.environ.get("CAMOUFLOW_GLINT_DRIVER_STAGE")
if driver_stage:
    if sys.platform != "win32":
        raise ValueError("Glint driver staging is Windows-only")
    sys.path.insert(0, str(ROOT))
    import playwright
    from scripts.native_driver_stage import bundle_datas
    a.datas = bundle_datas(a.datas, Path(playwright.__file__).parent, Path(driver_stage))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CamouFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "logo.ico") if sys.platform == "win32" else "NONE",
    version=APP_VERSION_INFO if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["node.exe"] if driver_stage else [],
    name="CamouFlow",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="CamouFlow.app",
        bundle_identifier="site.camouflow.desktop",
        info_plist={"NSHighResolutionCapable": True},
    )
