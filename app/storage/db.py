import json
import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOGGER = logging.getLogger(__name__)

# Keep data paths at project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SETTINGS_DIR = PROJECT_ROOT / "settings"
SETTINGS_DIR.mkdir(exist_ok=True)
ACCOUNTS_FILE = SETTINGS_DIR / "accounts.json"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
PROFILES_DIR = PROJECT_ROOT / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)
SCENARIOS_DIR = PROJECT_ROOT / "scenaries"
SCENARIOS_DIR.mkdir(exist_ok=True)

CAMOUFOX_DEFAULTS: Dict[str, Any] = {
    "headless": False,
    "humanize": True,
    "locale": "",
    "timezone": "",
    "os": [],
    "fonts": [],
    "window_width": 0,
    "window_height": 0,
    "persistent_context": True,
    "enable_cache": True,
    "block_webrtc": False,
    "block_images": False,
    "block_webgl": False,
    "disable_coop": False,
    "addons": [],
    "exclude_addons": [],
    "navigator_overrides": {},
    "window_overrides": {},
}

SAMPLE_SCENARIO = {
    "name": "Demo scenario",
    "description": "Sample scenario",
    "steps": [
        {"action": "goto", "url": "https://example.com", "wait_until": "load", "label": "start"},
        {"action": "wait_element", "selector": "body", "selector_type": "css", "timeout_ms": 10000},
        {"action": "sleep", "seconds": 1.5},
    ],
}
sample_steps = SAMPLE_SCENARIO["steps"]


def get_defined_stages() -> List[str]:
    """
    Return user-defined stages from settings; no built-in defaults.
    """
    try:
        settings = _load_settings()
        raw = settings.get("stages_json") if isinstance(settings, dict) else None
        if isinstance(raw, str):
            import json

            return list(json.loads(raw))
        if isinstance(raw, list):
            return [str(v) for v in raw]
    except Exception:
        LOGGER.exception("Failed to load stages from settings")
        return []
    return []


@dataclass
class Scenario:
    name: str
    steps: List[Dict]
    description: Optional[str] = None


def _safe_profile_name(email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", email or "profile")


def profile_dir_for_email(email: str) -> Path:
    return PROFILES_DIR / _safe_profile_name(email)


def _safe_scenario_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", name.strip() or "scenario")
    return cleaned[:120]


def _scenario_path(name: str) -> Path:
    return SCENARIOS_DIR / f"{_safe_scenario_name(name)}.json"


def _scenario_file_for_name(name: str) -> Path:
    """Return the file path for a scenario name, falling back to scanning all files."""
    direct = _scenario_path(name)
    if direct.exists():
        return direct
    for path in SCENARIOS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if str(data.get("name") or path.stem) == name:
                return path
        except Exception:
            continue
    return direct


def _ensure_storage() -> None:
    PROFILES_DIR.mkdir(exist_ok=True)
    SCENARIOS_DIR.mkdir(exist_ok=True)
    if not ACCOUNTS_FILE.exists():
        _atomic_write_text(ACCOUNTS_FILE, "[]", encoding="utf-8")
    if not SETTINGS_FILE.exists():
        _atomic_write_text(SETTINGS_FILE, "{}", encoding="utf-8")


def _next_profile_name(existing: List[Dict[str, Any]]) -> str:
    """
    Pick the next available profile name: profile1, profile2, etc.
    """
    max_num = 0
    for acc in existing:
        name = str(acc.get("name") or acc.get("email") or "")
        match = re.search(r"profile[_-]?(\d+)$", name.strip().lower())
        if match:
            try:
                num = int(match.group(1))
                max_num = max(max_num, num)
            except Exception:
                continue
    return f"profile{max_num + 1}"


def init_db() -> None:
    """
    Initialize JSON storage.
    """
    _ensure_storage()

    # Seed sample scenario in filesystem storage if none exist
    if not any(SCENARIOS_DIR.glob("*.json")):
        sample_path = SCENARIOS_DIR / "demo_scenario.json"
        sample_payload = {
            "name": "Demo scenario",
            "description": "Sample scenario",
            "steps": sample_steps,
        }
        try:
            sample_path.write_text(json.dumps(sample_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def _load_accounts_raw() -> List[Dict]:
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        LOGGER.exception("Failed to load accounts.json")
        return []


def _save_accounts_raw(accounts: List[Dict]) -> None:
    payload = json.dumps(accounts, ensure_ascii=False, indent=2)
    _atomic_write_text(ACCOUNTS_FILE, payload, encoding="utf-8")


def _normalize_account(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a plain dict with mandatory keys ensured; keeps all extra keys."""
    data: Dict[str, Any] = {}
    for key, val in (payload or {}).items():
        data[key] = val
    data["name"] = str(data.get("name") or "").strip()
    if not data["name"]:
        data["name"] = _next_profile_name(_load_accounts_raw())
    try:
        data["proxy_port"] = int(data["proxy_port"]) if data.get("proxy_port") not in (None, "") else None
    except Exception:
        data["proxy_port"] = None
    data["proxy_host"] = str(data.get("proxy_host") or "").strip()
    data["proxy_user"] = str(data.get("proxy_user") or "").strip()
    data["proxy_password"] = str(data.get("proxy_password") or "").strip()
    data["stage"] = "" if data.get("stage") is None else str(data.get("stage"))
    return data


def db_add_account(account: Dict[str, Any]) -> Dict[str, Any]:
    accounts = _load_accounts_raw()
    normalized = _normalize_account(account)
    ids_lower = {str(acc.get("name") or "").lower() for acc in accounts}
    acc_id = str(normalized.get("name") or "")
    if acc_id and acc_id.lower() in ids_lower:
        raise ValueError("Duplicate account identifier")
    accounts.append(normalized)
    _save_accounts_raw(accounts)
    return normalized


def db_get_accounts() -> List[Dict[str, Any]]:
    accounts: List[Dict[str, Any]] = []
    for payload in _load_accounts_raw():
        try:
            acc = _normalize_account(payload)
            accounts.append(acc)
        except Exception:
            continue
    return accounts


def db_delete_account(account_name: str) -> None:
    accounts = _load_accounts_raw()
    key = str(account_name or "").lower()
    filtered = [acc for acc in accounts if str(acc.get("name") or "").lower() != key]
    _save_accounts_raw(filtered)


def db_update_stage(account_name: str, stage: Optional[str]) -> None:
    accounts = _load_accounts_raw()
    updated = []
    key = str(account_name or "").lower()
    for acc in accounts:
        if str(acc.get("name") or "").lower() == key:
            acc["stage"] = stage
        updated.append(acc)
    _save_accounts_raw(updated)


def db_update_account(account_name: str, updates: Dict[str, Any]) -> None:
    """
    Update an account by its identifier (name), allowing all fields including name to change.
    """
    accounts = _load_accounts_raw()
    key = str(account_name or "").lower()
    idx = next((i for i, acc in enumerate(accounts) if str(acc.get("name") or "").lower() == key), -1)
    if idx < 0:
        raise ValueError("Account not found")
    current = accounts[idx]
    merged: Dict[str, Any] = {**current, **(updates or {})}

    delete_keys = merged.pop("__delete_keys__", []) or []
    if delete_keys:
        for k in delete_keys:
            if k == "name":
                continue
            merged.pop(k, None)

    new_name = str(merged.get("name") or "")
    for i, acc in enumerate(accounts):
        if i == idx:
            continue
        if str(acc.get("name") or "").lower() == new_name.lower():
            raise ValueError("Duplicate account identifier")

    normalized = _normalize_account(merged)
    accounts[idx] = normalized
    _save_accounts_raw(accounts)

    # Rename profile directory if the identifier changed.
    old_profile = profile_dir_for_email(str(current.get("name") or ""))
    new_profile = profile_dir_for_email(str(normalized.get("name") or ""))
    if old_profile != new_profile and old_profile.exists():
        try:
            old_profile.rename(new_profile)
        except Exception:
            pass


def _load_settings() -> Dict[str, str]:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        LOGGER.exception("Failed to load settings.json")
        return {}


def _save_settings(settings: Dict[str, str]) -> None:
    payload = json.dumps(settings, ensure_ascii=False, indent=2)
    _atomic_write_text(SETTINGS_FILE, payload, encoding="utf-8")


def _atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """
    Write text to a temp file and atomically replace the target.
    This avoids partially-written JSON on crashes or concurrent writes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def db_get_setting(key: str) -> Optional[str]:
    settings = _load_settings()
    val = settings.get(key)
    if val is None:
        return None
    return str(val)


def db_set_setting(key: str, value: str) -> None:
    settings = _load_settings()
    settings[key] = value
    _save_settings(settings)


def db_get_camoufox_defaults() -> Dict[str, Any]:
    raw = db_get_setting("camoufox_defaults")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                combined = dict(CAMOUFOX_DEFAULTS)
                combined.update({k: data.get(k) for k in CAMOUFOX_DEFAULTS.keys() if k in data})
                return combined
        except Exception:
            pass
    return dict(CAMOUFOX_DEFAULTS)


def db_set_camoufox_defaults(settings: Dict[str, Any]) -> None:
    merged = dict(CAMOUFOX_DEFAULTS)
    for key in CAMOUFOX_DEFAULTS.keys():
        if key in settings:
            merged[key] = settings[key]
    db_set_setting("camoufox_defaults", json.dumps(merged, ensure_ascii=False))


def db_get_selector_indices() -> Dict[str, int]:
    settings = _load_settings()
    mapping = settings.get("selector_indices")
    if isinstance(mapping, dict):
        try:
            return {str(k): int(v) for k, v in mapping.items()}
        except Exception:
            return {}
    return {}


def db_get_selector_index(selector: str) -> Optional[int]:
    mapping = db_get_selector_indices()
    val = mapping.get(selector)
    if val is None:
        return None
    try:
        return int(val)
    except Exception:
        return None


def db_set_selector_index(selector: str, index: int) -> None:
    settings = _load_settings()
    mapping = settings.get("selector_indices")
    if not isinstance(mapping, dict):
        mapping = {}
    try:
        mapping[str(selector)] = int(index)
    except Exception:
        mapping[str(selector)] = index
    settings["selector_indices"] = mapping
    _save_settings(settings)


def db_set_selector_indices(mapping: Dict[str, int]) -> None:
    if not isinstance(mapping, dict):
        return
    try:
        normalized = {str(k): int(v) for k, v in mapping.items()}
    except Exception:
        normalized = {str(k): v for k, v in mapping.items()}
    settings = _load_settings()
    settings["selector_indices"] = normalized
    _save_settings(settings)


def db_delete_selector_index(selector: str) -> None:
    settings = _load_settings()
    mapping = settings.get("selector_indices")
    if not isinstance(mapping, dict):
        return
    mapping.pop(str(selector), None)
    settings["selector_indices"] = mapping
    _save_settings(settings)


def db_get_scenarios() -> List[Scenario]:
    scenarios: List[Scenario] = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = str(data.get("name") or path.stem)
            steps = data.get("steps") or []
            desc = data.get("description")
            scenarios.append(Scenario(name=name, steps=steps, description=desc))
        except Exception:
            continue
    scenarios.sort(key=lambda s: s.name)
    return scenarios


def db_get_scenario(name: str) -> Optional[Scenario]:
    path = _scenario_file_for_name(name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        steps = data.get("steps") or []
        desc = data.get("description")
        real_name = data.get("name") or name
        return Scenario(name=str(real_name), steps=steps, description=desc)
    except Exception:
        return None


def db_get_scenario_path(name: str) -> Path:
    """
    Return the JSON file path for a scenario name, scanning existing scenario files
    when necessary (e.g. if the file name differs from the stored scenario name).
    """
    return _scenario_file_for_name(name)


def db_save_scenario(name: str, steps: List[Dict], description: Optional[str] = None) -> None:
    existing = _scenario_file_for_name(name)
    path = existing if existing.exists() else _scenario_path(name)
    payload = {"name": name, "description": description, "steps": steps or []}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def db_delete_scenario(name: str) -> None:
    path = _scenario_file_for_name(name)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def cleanup_profiles(accounts: List[Dict[str, Any]]) -> None:
    existing = {_safe_profile_name(str(acc.get("name") or acc.get("email") or "")) for acc in accounts}
    for item in PROFILES_DIR.iterdir():
        if item.is_dir() and item.name not in existing:
            shutil.rmtree(item, ignore_errors=True)


def delete_profile_for_account(name: str) -> None:
    path = profile_dir_for_email(name)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def clear_profile_cookies(name: str) -> bool:
    """
    Remove the entire profile directory to reset cookies/storage without deleting the account.
    """
    profile_path = profile_dir_for_email(name)
    if not profile_path.exists():
        return False

    try:
        shutil.rmtree(profile_path)
    except OSError as exc:
        raise RuntimeError(f"Cannot remove profile directory {profile_path}: {exc}") from exc
    return True

# Backward compatibility name
delete_profile_for_email = delete_profile_for_account
