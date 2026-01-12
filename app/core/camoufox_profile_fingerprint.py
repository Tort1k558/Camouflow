import json
import logging
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from browserforge.fingerprints.generator import Fingerprint, NavigatorFingerprint, ScreenFingerprint
from camoufox.fingerprints import generate_fingerprint
from camoufox.webgl.sample import sample_webgl

_FINGERPRINT_FILE = "camoufox_fingerprint.json"
_SCHEMA_VERSION = 3


def _fingerprint_path(profile_dir: Path) -> Path:
    return Path(profile_dir) / _FINGERPRINT_FILE


def _fingerprint_from_dict(payload: Dict) -> Fingerprint:
    screen_raw = payload.get("screen") or {}
    navigator_raw = payload.get("navigator") or {}
    screen = ScreenFingerprint(**screen_raw)
    navigator = NavigatorFingerprint(**navigator_raw)
    return Fingerprint(
        screen=screen,
        navigator=navigator,
        headers=dict(payload.get("headers") or {}),
        videoCodecs=dict(payload.get("videoCodecs") or {}),
        audioCodecs=dict(payload.get("audioCodecs") or {}),
        pluginsData=dict(payload.get("pluginsData") or {}),
        battery=payload.get("battery"),
        videoCard=payload.get("videoCard"),
        multimediaDevices=list(payload.get("multimediaDevices") or []),
        fonts=list(payload.get("fonts") or []),
        mockWebRTC=payload.get("mockWebRTC"),
        slim=payload.get("slim"),
    )


def _stable_overrides_from_dict(payload: Dict) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    overrides: Dict[str, Any] = {}
    for key in ("window.history.length", "fonts:spacing_seed", "canvas:aaOffset"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            overrides[key] = int(value)
    return overrides


def _generate_stable_overrides() -> Dict[str, int]:
    return {
        "window.history.length": random.randint(1, 5),
        "fonts:spacing_seed": random.randint(0, 1_073_741_823),
        "canvas:aaOffset": random.randint(-50, 50),
    }


def _target_os_from_user_agent(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "windows" in ua:
        return "win"
    if "mac" in ua:
        return "mac"
    return "lin"


def _webgl_pair_from_dict(payload: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    if not isinstance(payload, dict):
        return None
    vendor = str(payload.get("webgl_vendor") or "").strip()
    renderer = str(payload.get("webgl_renderer") or "").strip()
    if vendor and renderer:
        return vendor, renderer
    return None


def _generate_webgl_pair(user_agent: str) -> Optional[Tuple[str, str]]:
    try:
        data = sample_webgl(_target_os_from_user_agent(user_agent))
    except Exception:
        return None
    vendor = str(data.get("webGl:vendor") or "").strip()
    renderer = str(data.get("webGl:renderer") or "").strip()
    if vendor and renderer:
        if not _webgl_pair_matches_user_agent(user_agent, renderer):
            return None
        return vendor, renderer
    return None


def _webgl_pair_matches_user_agent(user_agent: str, renderer: str) -> bool:
    ua = (user_agent or "").lower()
    renderer_l = (renderer or "").lower()
    if "macintosh" in ua and "intel" in ua:
        if "apple m" in renderer_l or "m1" in renderer_l or "m2" in renderer_l or "m3" in renderer_l:
            return False
    if "macintosh" in ua and ("arm" in ua or "aarch" in ua):
        if "intel" in renderer_l:
            return False
    return True


def _fingerprint_gpu_matches_ua(fp: Fingerprint) -> bool:
    renderer = ""
    if getattr(fp, "videoCard", None):
        renderer = str(getattr(fp.videoCard, "renderer", "") or "")
    return _webgl_pair_matches_user_agent(fp.navigator.userAgent, renderer)


def load_or_create_profile_fingerprint_bundle(
    profile_dir: Path,
    *,
    os_payload: Optional[object] = None,
    window: Optional[tuple[int, int]] = None,
    logger: Optional[logging.Logger] = None,
) -> Tuple[Fingerprint, Dict[str, Any], Optional[Tuple[str, str]]]:
    """
    Generate a Camoufox-style fingerprint and persist it per profile, along with
    stable overrides used to keep per-profile randomness consistent.
    """
    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    path = _fingerprint_path(profile_dir)

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or int(data.get("version") or 0) != _SCHEMA_VERSION:
                raise ValueError("Unsupported fingerprint schema")
            fp_raw = data.get("fingerprint")
            if not isinstance(fp_raw, dict):
                raise ValueError("Fingerprint payload missing")
            overrides = _stable_overrides_from_dict(data.get("overrides") or {})
            fp = _fingerprint_from_dict(fp_raw)
            if _fingerprint_gpu_matches_ua(fp):
                return (
                    fp,
                    overrides,
                    _webgl_pair_from_dict(data.get("overrides") or {}),
                )
            if logger:
                logger.warning("Fingerprint GPU mismatch for %s; regenerating", str(profile_dir))
        except Exception as exc:
            if logger:
                logger.warning("Failed to load Camoufox fingerprint from %s: %s", str(path), exc)

    fp = generate_fingerprint(window=window, os=os_payload)
    for _ in range(4):
        if _fingerprint_gpu_matches_ua(fp):
            break
        fp = generate_fingerprint(window=window, os=os_payload)
    overrides = _generate_stable_overrides()
    webgl_pair = _generate_webgl_pair(fp.navigator.userAgent)
    if webgl_pair:
        overrides["webgl_vendor"] = webgl_pair[0]
        overrides["webgl_renderer"] = webgl_pair[1]
    payload = {
        "version": _SCHEMA_VERSION,
        "fingerprint": asdict(fp),
        "overrides": overrides,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    if logger:
        logger.info("Camoufox fingerprint saved to %s", str(path))
    return fp, overrides, webgl_pair


def load_or_create_profile_fingerprint(
    profile_dir: Path,
    *,
    os_payload: Optional[object] = None,
    window: Optional[tuple[int, int]] = None,
    logger: Optional[logging.Logger] = None,
) -> Fingerprint:
    """
    Generate a Camoufox-style fingerprint and persist it per profile.
    """
    fp, _ = load_or_create_profile_fingerprint_bundle(
        profile_dir,
        os_payload=os_payload,
        window=window,
        logger=logger,
    )
    return fp
