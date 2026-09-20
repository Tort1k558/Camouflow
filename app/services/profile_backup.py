"""Checksummed profile archives, restored only into a new local identity."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from app.storage import db

MAX_BYTES = 2 * 1024 ** 3
MAX_FILES = 50000


def export_profile(name: str, target: Path, sessions: bool, secrets: bool) -> None:
    account = next((a for a in db.db_get_accounts() if a["name"] == name), None)
    if account is None:
        raise ValueError("Local profile not found")
    if not secrets:
        account = {k: v for k, v in account.items() if k in {"name", "stage", "_browser_engine"}}
    metadata = {"profile": account, "sessions": sessions, "secrets": secrets, "scenarios": [], "settings": {}}
    if secrets:
        metadata["scenarios"] = [{"name": s.name, "steps": s.steps, "description": s.description} for s in db.db_get_scenarios()]
        metadata["settings"] = {k: db.db_get_setting(k) for k in ("camoufox_defaults", "cloakbrowser_defaults", "browser_engine")}
    files = {}
    source_root = db.profile_dir_for_email(name)
    if source_root.is_symlink() or source_root.is_junction():
        raise ValueError("Profile directory must not be a filesystem link")
    root = source_root.resolve()
    if not root.is_relative_to(db.PROFILES_DIR.resolve()) or root == db.PROFILES_DIR.resolve():
        raise ValueError("Invalid profile storage path")
    if sessions and root.exists():
        if target.resolve().is_relative_to(root):
            raise ValueError("Save the archive outside the browser profile")
        for path in root.rglob("*"):
            if path.is_symlink() or path.is_junction():
                raise ValueError("Profile contains a symbolic link; close the browser and remove the link before exporting")
            if path.is_file() and path.name not in {"parent.lock", "SingletonLock", "SingletonCookie", "SingletonSocket"}:
                files["browser/" + path.relative_to(root).as_posix()] = path
    if len(files) > MAX_FILES or sum(p.stat().st_size for p in files.values()) > MAX_BYTES:
        raise ValueError("Archive safety limit: 2 GiB / 50,000 files")
    hashes = {}
    created = False
    try:
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            created = True
            payload = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
            archive.writestr("profile.json", payload)
            if len(payload) > 8 * 1024 * 1024:
                raise ValueError("Profile metadata exceeds 8 MiB")
            hashes["profile.json"] = hashlib.sha256(payload).hexdigest()
            for name, path in files.items():
                before = path.stat()
                digest = hashlib.sha256()
                with path.open("rb") as source, archive.open(name, "w", force_zip64=True) as destination:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        destination.write(chunk)
                        digest.update(chunk)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("Profile changed during export; close its browser and retry")
                hashes[name] = digest.hexdigest()
            archive.writestr("manifest.json", json.dumps({"format": 1, "sha256": hashes}))
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise


def restore_profile(source: Path, new_name: str, import_scenarios: bool = False) -> Path:
    new_name = new_name.strip()
    if not new_name or len(new_name) > 80 or db._safe_profile_name(new_name) in {".", ".."} or _unsafe_windows_name(db._safe_profile_name(new_name)):
        raise ValueError("Enter a valid new profile name")
    if any(a["name"].casefold() == new_name.casefold() for a in db.db_get_accounts()):
        raise ValueError("Profile already exists; choose a new name")
    target = db.profile_dir_for_email(new_name).resolve()
    if not target.is_relative_to(db.PROFILES_DIR.resolve()) or target.exists():
        raise ValueError("Profile storage already exists or is outside the workspace")
    db.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=db.PROFILES_DIR) as temp:
        stage = Path(temp)
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES + 2 or sum(i.file_size for i in entries) > MAX_BYTES:
                raise ValueError("Archive exceeds safety limits")
            seen = set()
            for entry in entries:
                name = entry.filename
                path = PurePosixPath(name)
                if (path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                        or name.casefold() in seen or stat.S_ISLNK(entry.external_attr >> 16)
                        or any(_unsafe_windows_name(p) for p in path.parts)):
                    raise ValueError("Unsafe archive path")
                seen.add(name.casefold())
            if archive.getinfo("manifest.json").file_size > 8 * 1024 * 1024:
                raise ValueError("Manifest too large")
            if archive.getinfo("profile.json").file_size > 8 * 1024 * 1024:
                raise ValueError("Profile metadata too large")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != 1 or set(manifest.get("sha256", {})) != {e.filename for e in entries} - {"manifest.json"}:
                raise ValueError("Invalid archive manifest")
            for name, expected in manifest["sha256"].items():
                if name != "profile.json" and not name.startswith("browser/"):
                    raise ValueError("Unexpected archive entry")
                digest = hashlib.sha256()
                destination = stage / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as src, destination.open("xb") as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        digest.update(chunk)
                        dst.write(chunk)
                if digest.hexdigest() != expected:
                    raise ValueError("Archive checksum mismatch")
        metadata = json.loads((stage / "profile.json").read_text(encoding="utf-8"))
        account = metadata["profile"]
        if not isinstance(account, dict):
            raise ValueError("Invalid profile metadata")
        account["name"] = new_name
        settings = metadata.get("settings", {})
        for engine in ("camoufox", "cloakbrowser"):
            defaults = json.loads(settings.get(engine + "_defaults") or "{}")
            overrides = account.get(engine + "_settings") or {}
            if not isinstance(defaults, dict) or not isinstance(overrides, dict):
                raise ValueError("Invalid engine settings")
            if defaults or overrides:
                account[engine + "_settings"] = {**defaults, **overrides}
        scenarios = metadata.get("scenarios", []) if import_scenarios else []
        if not isinstance(scenarios, list) or any(not isinstance(s, dict) or not isinstance(s.get("steps"), list) for s in scenarios):
            raise ValueError("Invalid scenarios")
        browser = stage / "browser"
        browser.mkdir(exist_ok=True)
        (browser / "camouflow-backup-settings.json").write_text(json.dumps({"settings": metadata.get("settings", {}), "scenarios": metadata.get("scenarios", [])}, ensure_ascii=False, indent=2), encoding="utf-8")
        with db._STORAGE_LOCK:
            if target.exists() or any(a["name"].casefold() == new_name.casefold() for a in db.db_get_accounts()):
                raise ValueError("Restore destination was created by another operation")
            browser.rename(target)
            created_scenarios = []
            try:
                planned_names = {}
                for index, scenario in enumerate(scenarios):
                    original = str(scenario.get("name") or "Scenario")
                    if original in planned_names:
                        raise ValueError("Duplicate scenario names in backup")
                    base = f"{new_name[:40]} restore {index + 1}"
                    candidate, suffix = base, 1
                    while db._scenario_path(candidate).exists() or candidate in planned_names.values():
                        suffix += 1
                        candidate = f"{base} ({suffix})"
                    planned_names[original] = candidate
                for scenario in scenarios:
                    candidate = planned_names[str(scenario.get("name") or "Scenario")]
                    steps = scenario["steps"]
                    # Nested scenario references are rewritten only when the target is in this archive.
                    for step in steps:
                        if isinstance(step, dict) and step.get("action") == "run_scenario":
                            for key in ("scenario", "scenario_name", "name", "value"):
                                if step.get(key) in planned_names:
                                    step[key] = planned_names[step[key]]
                    path = db._scenario_path(candidate)
                    created_scenarios.append(path)
                    db.db_save_scenario(candidate, steps, scenario.get("description"))
                db.db_add_account(account)
            except Exception:
                for path in created_scenarios:
                    path.unlink(missing_ok=True)
                shutil.rmtree(target)
                raise
    return target


def _unsafe_windows_name(name: str) -> bool:
    stem = name.split(".", 1)[0].upper()
    return (name.endswith((".", " ")) or stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            or stem in {f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)}
            or any(ord(c) < 32 or c in '<>"|?*' for c in name))
