# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH).resolve()

datas = [
    (str(ROOT / "logo.ico"), "."),
    (str(ROOT / "scenaries"), "scenaries"),
]

datas += collect_data_files("browserforge")
hiddenimports = collect_submodules("browserforge")

# camoufox ships non-.py assets (e.g. YAML manifests) that must be bundled.
datas += collect_data_files("camoufox")
hiddenimports += collect_submodules("camoufox")

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
    icon=str(ROOT / "logo.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CamouFlow",
)
