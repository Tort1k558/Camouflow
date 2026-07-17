"""Browser settings bridge for QML."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.storage.db import (
    CAMOUFOX_DEFAULTS,
    CLOAKBROWSER_DEFAULTS,
    db_get_browser_engine,
    db_get_camoufox_defaults,
    db_get_cloakbrowser_defaults,
    db_set_browser_engine,
    db_set_camoufox_defaults,
    db_set_cloakbrowser_defaults,
)


_INT_KEYS = {
    "hardware_concurrency",
    "device_memory",
    "window_width",
    "window_height",
    "screen_width",
    "screen_height",
    "fingerprint_seed",
    "storage_quota",
    "human_typing_delay_min",
    "human_typing_delay_max",
    "human_scroll_intensity",
}
_FLOAT_KEYS = {"human_mouse_speed"}
_BOOL_KEYS = {
    "persistent_context",
    "enable_cache",
    "block_webrtc",
    "block_images",
    "block_webgl",
    "disable_coop",
    "geoip",
    "stealth_args",
    "fingerprint_noise",
    "disable_http2",
    "ignore_https_errors",
    "java_script_enabled",
    "bypass_csp",
    "accept_downloads",
    "human_actionability_wait",
}
_LIST_KEYS = {"fonts", "addons", "exclude_addons", "extension_paths", "launch_args", "permissions"}
_DICT_KEYS = {"extra_http_headers"}


class BrowserSettingsBridge(QObject):
    changed = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, app_state=None, parent=None) -> None:
        super().__init__(parent)
        self._app_state = app_state
        self._engine = db_get_browser_engine()
        self._camoufox = db_get_camoufox_defaults()
        self._cloak = db_get_cloakbrowser_defaults()
        if app_state is not None:
            app_state.refreshRequested.connect(self.reload)

    def _active(self) -> Dict[str, Any]:
        return self._cloak if self._engine == "cloakbrowser" else self._camoufox

    def _emit_message(self, text: str) -> None:
        self.message.emit(text)
        if self._app_state is not None:
            self._app_state.notify(text)

    @staticmethod
    def _text_list(raw: Any) -> List[str]:
        if isinstance(raw, str):
            parts = raw.replace("\r", "\n").split("\n")
        elif isinstance(raw, Iterable):
            parts = [str(v) for v in raw]
        else:
            parts = []
        return [p.strip() for p in parts if p and p.strip()]

    def _list_text(self, key: str) -> str:
        return "\n".join(self._text_list(self._active().get(key)))

    def _int_value(self, key: str, default: int = 0) -> int:
        try:
            return int(self._active().get(key) or default)
        except Exception:
            return default

    def _float_value(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self._active().get(key) or default)
        except Exception:
            return default

    def _bool_value(self, key: str, default: bool = False) -> bool:
        return bool(self._active().get(key, default))

    def _dict_text(self, key: str) -> str:
        import json

        payload = self._active().get(key)
        return json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=False, indent=2)

    def _set_active_value(self, key: str, value: Any) -> None:
        data = self._active()
        if key in _INT_KEYS:
            try:
                value = int(value)
            except Exception:
                value = 0
        elif key in _FLOAT_KEYS:
            try:
                value = round(float(value), 3)
            except Exception:
                value = 0
        elif key in _BOOL_KEYS:
            value = bool(value)
        elif key in _LIST_KEYS:
            value = self._text_list(value)
        elif key in _DICT_KEYS and isinstance(value, str):
            import json

            try:
                parsed = json.loads(value or "{}")
                value = parsed if isinstance(parsed, dict) else {}
            except Exception:
                self._emit_message(f"{key} must be valid JSON object")
                return
        elif key == "headless":
            if value in (True, "true", "headless"):
                value = True
            elif str(value).lower() == "virtual":
                value = "virtual"
            else:
                value = False
        elif key == "humanize":
            if isinstance(value, str):
                val = value.strip().lower()
                if val in {"false", "0", "off", "no"}:
                    value = False
                elif val in {"true", "1", "on", "yes"}:
                    value = True
                else:
                    try:
                        value = max(0.1, round(float(value), 2))
                    except Exception:
                        value = True
        if key == "user_agent" and self._engine == "camoufox":
            overrides = data.get("navigator_overrides")
            if not isinstance(overrides, dict):
                overrides = {}
                data["navigator_overrides"] = overrides
            if str(value or "").strip():
                overrides["userAgent"] = str(value).strip()
            else:
                overrides.pop("userAgent", None)
            return
        if key == "hardware_concurrency" and self._engine == "camoufox":
            overrides = data.get("navigator_overrides")
            if not isinstance(overrides, dict):
                overrides = {}
                data["navigator_overrides"] = overrides
            if int(value or 0) > 0:
                overrides["hardwareConcurrency"] = int(value)
            else:
                overrides.pop("hardwareConcurrency", None)
            return
        if key == "webgl_vendor":
            data["gpu_vendor"] = value
        if key == "webgl_renderer":
            data["gpu_renderer"] = value
        if key in {"navigator_overrides", "window_overrides"} and isinstance(value, str):
            import json

            try:
                parsed = json.loads(value or "{}")
                value = parsed if isinstance(parsed, dict) else {}
            except Exception:
                self._emit_message(f"{key} must be valid JSON object")
                return
        data[key] = value

    @pyqtProperty(str, notify=changed)
    def engine(self) -> str:
        return self._engine

    @pyqtProperty(str, notify=changed)
    def locale(self) -> str:
        return str(self._active().get("locale") or "")

    @pyqtProperty(str, notify=changed)
    def timezone(self) -> str:
        return str(self._active().get("timezone") or "")

    @pyqtProperty(str, notify=changed)
    def userAgent(self) -> str:  # noqa: N802
        data = self._active()
        overrides = data.get("navigator_overrides") if isinstance(data.get("navigator_overrides"), dict) else {}
        return str(data.get("user_agent") or overrides.get("userAgent") or "")

    @pyqtProperty(int, notify=changed)
    def cpuCores(self) -> int:  # noqa: N802
        data = self._active()
        overrides = data.get("navigator_overrides") if isinstance(data.get("navigator_overrides"), dict) else {}
        return self._int_value("hardware_concurrency", int(overrides.get("hardwareConcurrency") or 0))

    @pyqtProperty(int, notify=changed)
    def memoryGb(self) -> int:  # noqa: N802
        return 16

    @pyqtProperty(int, notify=changed)
    def fingerprintSeed(self) -> int:  # noqa: N802
        return self._int_value("fingerprint_seed")

    @pyqtProperty(bool, notify=changed)
    def stealthArgs(self) -> bool:  # noqa: N802
        return self._bool_value("stealth_args", True)

    @pyqtProperty(str, notify=changed)
    def backend(self) -> str:
        return str(self._active().get("backend") or "")

    @pyqtProperty(str, notify=changed)
    def webglVendor(self) -> str:  # noqa: N802
        return str(self._active().get("webgl_vendor") or self._active().get("gpu_vendor") or "")

    @pyqtProperty(str, notify=changed)
    def webglRenderer(self) -> str:  # noqa: N802
        return str(self._active().get("webgl_renderer") or self._active().get("gpu_renderer") or "")

    @pyqtProperty(str, notify=changed)
    def platform(self) -> str:
        return str(self._active().get("platform") or "windows")

    @pyqtProperty(str, notify=changed)
    def headlessMode(self) -> str:  # noqa: N802
        value = self._active().get("headless", False)
        if value == "virtual":
            return "virtual"
        return "headless" if bool(value) else "standard"

    @pyqtProperty(bool, notify=changed)
    def humanize(self) -> bool:
        return self._active().get("humanize", True) is not False

    @pyqtProperty(str, notify=changed)
    def humanizeDuration(self) -> str:  # noqa: N802
        value = self._active().get("humanize", True)
        return str(value) if not isinstance(value, bool) else ""

    @pyqtProperty(str, notify=changed)
    def humanPreset(self) -> str:  # noqa: N802
        return str(self._active().get("human_preset") or "default")

    @pyqtProperty(str, notify=changed)
    def humanMouseSpeed(self) -> str:  # noqa: N802
        value = self._float_value("human_mouse_speed")
        return "" if value <= 0 else str(value)

    @pyqtProperty(int, notify=changed)
    def humanTypingDelayMin(self) -> int:  # noqa: N802
        return self._int_value("human_typing_delay_min")

    @pyqtProperty(int, notify=changed)
    def humanTypingDelayMax(self) -> int:  # noqa: N802
        return self._int_value("human_typing_delay_max")

    @pyqtProperty(int, notify=changed)
    def humanScrollIntensity(self) -> int:  # noqa: N802
        return self._int_value("human_scroll_intensity")

    @pyqtProperty(bool, notify=changed)
    def humanActionabilityWait(self) -> bool:  # noqa: N802
        return self._bool_value("human_actionability_wait", True)

    @pyqtProperty(bool, notify=changed)
    def osAuto(self) -> bool:  # noqa: N802
        return not bool(self._active().get("os") or [])

    def _os_enabled(self, os_name: str) -> bool:
        return os_name in set(self._text_list(self._active().get("os")))

    @pyqtProperty(bool, notify=changed)
    def osWindows(self) -> bool:  # noqa: N802
        return self._os_enabled("windows")

    @pyqtProperty(bool, notify=changed)
    def osMacos(self) -> bool:  # noqa: N802
        return self._os_enabled("macos")

    @pyqtProperty(bool, notify=changed)
    def osLinux(self) -> bool:  # noqa: N802
        return self._os_enabled("linux")

    @pyqtProperty(int, notify=changed)
    def windowWidth(self) -> int:  # noqa: N802
        return self._int_value("window_width")

    @pyqtProperty(int, notify=changed)
    def windowHeight(self) -> int:  # noqa: N802
        return self._int_value("window_height")

    @pyqtProperty(int, notify=changed)
    def screenWidth(self) -> int:  # noqa: N802
        return self._int_value("screen_width", self.windowWidth)

    @pyqtProperty(int, notify=changed)
    def screenHeight(self) -> int:  # noqa: N802
        return self._int_value("screen_height", self.windowHeight)

    @pyqtProperty(int, notify=changed)
    def deviceMemory(self) -> int:  # noqa: N802
        return self._int_value("device_memory")

    @pyqtProperty(bool, notify=changed)
    def persistentContext(self) -> bool:  # noqa: N802
        return self._bool_value("persistent_context", True)

    @pyqtProperty(bool, notify=changed)
    def enableCache(self) -> bool:  # noqa: N802
        return self._bool_value("enable_cache", True)

    @pyqtProperty(bool, notify=changed)
    def blockWebrtc(self) -> bool:  # noqa: N802
        return self._bool_value("block_webrtc")

    @pyqtProperty(bool, notify=changed)
    def blockImages(self) -> bool:  # noqa: N802
        return self._bool_value("block_images")

    @pyqtProperty(bool, notify=changed)
    def blockWebgl(self) -> bool:  # noqa: N802
        return self._bool_value("block_webgl")

    @pyqtProperty(bool, notify=changed)
    def disableCoop(self) -> bool:  # noqa: N802
        return self._bool_value("disable_coop")

    @pyqtProperty(bool, notify=changed)
    def geoip(self) -> bool:
        return self._bool_value("geoip")

    @pyqtProperty(str, notify=changed)
    def platformVersion(self) -> str:  # noqa: N802
        return str(self._active().get("platform_version") or "")

    @pyqtProperty(str, notify=changed)
    def brand(self) -> str:
        return str(self._active().get("brand") or "")

    @pyqtProperty(str, notify=changed)
    def brandVersion(self) -> str:  # noqa: N802
        return str(self._active().get("brand_version") or "")

    @pyqtProperty(int, notify=changed)
    def storageQuota(self) -> int:  # noqa: N802
        return self._int_value("storage_quota")

    @pyqtProperty(bool, notify=changed)
    def fingerprintNoise(self) -> bool:  # noqa: N802
        return self._bool_value("fingerprint_noise", True)

    @pyqtProperty(str, notify=changed)
    def webrtcIp(self) -> str:  # noqa: N802
        return str(self._active().get("webrtc_ip") or "")

    @pyqtProperty(str, notify=changed)
    def proxyBypass(self) -> str:  # noqa: N802
        return str(self._active().get("proxy_bypass") or "")

    @pyqtProperty(bool, notify=changed)
    def disableHttp2(self) -> bool:  # noqa: N802
        return self._bool_value("disable_http2")

    @pyqtProperty(str, notify=changed)
    def colorScheme(self) -> str:  # noqa: N802
        return str(self._active().get("color_scheme") or "")

    @pyqtProperty(str, notify=changed)
    def permissionsText(self) -> str:  # noqa: N802
        return self._list_text("permissions")

    @pyqtProperty(str, notify=changed)
    def extraHttpHeadersText(self) -> str:  # noqa: N802
        return self._dict_text("extra_http_headers")

    @pyqtProperty(str, notify=changed)
    def storageStatePath(self) -> str:  # noqa: N802
        return str(self._active().get("storage_state_path") or "")

    @pyqtProperty(bool, notify=changed)
    def ignoreHttpsErrors(self) -> bool:  # noqa: N802
        return self._bool_value("ignore_https_errors")

    @pyqtProperty(bool, notify=changed)
    def javaScriptEnabled(self) -> bool:  # noqa: N802
        return self._bool_value("java_script_enabled", True)

    @pyqtProperty(bool, notify=changed)
    def bypassCsp(self) -> bool:  # noqa: N802
        return self._bool_value("bypass_csp")

    @pyqtProperty(bool, notify=changed)
    def acceptDownloads(self) -> bool:  # noqa: N802
        return self._bool_value("accept_downloads", True)

    @pyqtProperty(str, notify=changed)
    def fontsText(self) -> str:  # noqa: N802
        return self._list_text("fonts")

    @pyqtProperty(str, notify=changed)
    def addonsText(self) -> str:  # noqa: N802
        return self._list_text("addons")

    @pyqtProperty(str, notify=changed)
    def excludeAddonsText(self) -> str:  # noqa: N802
        return self._list_text("exclude_addons")

    @pyqtProperty(str, notify=changed)
    def extensionPathsText(self) -> str:  # noqa: N802
        return self._list_text("extension_paths")

    @pyqtProperty(str, notify=changed)
    def launchArgsText(self) -> str:  # noqa: N802
        return self._list_text("launch_args")

    @pyqtProperty(str, notify=changed)
    def navigatorOverridesText(self) -> str:  # noqa: N802
        import json

        payload = self._active().get("navigator_overrides")
        return json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=False, indent=2)

    @pyqtProperty(str, notify=changed)
    def windowOverridesText(self) -> str:  # noqa: N802
        import json

        payload = self._active().get("window_overrides")
        return json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=False, indent=2)

    @pyqtSlot()
    def reload(self) -> None:
        self._engine = db_get_browser_engine()
        self._camoufox = db_get_camoufox_defaults()
        self._cloak = db_get_cloakbrowser_defaults()
        self.changed.emit()

    @pyqtSlot(str)
    def setEngine(self, engine: str) -> None:  # noqa: N802
        normalized = str(engine or "camoufox").lower()
        if normalized not in {"camoufox", "cloakbrowser"}:
            normalized = "camoufox"
        self._engine = normalized
        db_set_browser_engine(self._engine)
        self.changed.emit()

    @pyqtSlot(str, "QVariant")
    def setValue(self, key: str, value: Any) -> None:  # noqa: N802
        key = str(key or "")
        if not key:
            return
        self._set_active_value(key, value)
        self.changed.emit()

    @pyqtSlot(str, bool)
    def setBool(self, key: str, value: bool) -> None:  # noqa: N802
        self.setValue(key, value)

    @pyqtSlot(str)
    def setHeadlessMode(self, mode: str) -> None:  # noqa: N802
        mode = str(mode or "standard").lower()
        self.setValue("headless", "virtual" if mode == "virtual" else mode == "headless")

    @pyqtSlot(bool)
    def setHumanizeEnabled(self, enabled: bool) -> None:  # noqa: N802
        self.setValue("humanize", True if enabled else False)

    @pyqtSlot(str, bool)
    def setOsEnabled(self, os_name: str, enabled: bool) -> None:  # noqa: N802
        name = str(os_name or "").lower()
        allowed = {"windows", "macos", "linux"}
        current = set(self._text_list(self._active().get("os")))
        if name == "auto":
            current.clear()
        elif name in allowed:
            if enabled:
                current.add(name)
            else:
                current.discard(name)
        self._active()["os"] = sorted(current)
        self.changed.emit()

    @pyqtSlot(str)
    def applyPreset(self, name: str) -> None:  # noqa: N802
        preset = str(name or "").strip().lower()
        data = self._active()
        if preset == "balanced":
            data.update({
                "headless": False,
                "humanize": True,
                "human_preset": "default",
                "geoip": self._engine == "cloakbrowser",
                "persistent_context": True,
            })
        elif preset == "maximum_stealth":
            data.update({
                "headless": False,
                "humanize": True,
                "human_preset": "careful",
                "geoip": self._engine == "cloakbrowser",
                "persistent_context": True,
                "stealth_args": True,
                "fingerprint_noise": True,
                "webrtc_ip": "auto",
            })
            if self._engine == "camoufox":
                data.update({"block_webrtc": True, "enable_cache": True})
        elif preset == "fingerprintjs":
            data.update({
                "headless": False,
                "geoip": self._engine == "cloakbrowser",
                "fingerprint_noise": False,
                "storage_quota": 500,
                "webrtc_ip": "auto",
            })
        elif preset == "cloudflare":
            data.update({
                "headless": False,
                "humanize": True,
                "human_preset": "careful",
                "geoip": self._engine == "cloakbrowser",
                "persistent_context": True,
                "webrtc_ip": "auto",
            })
        elif preset == "low_resource":
            data.update({
                "headless": True,
                "humanize": False,
                "block_images": True,
                "enable_cache": False,
                "window_width": 1280,
                "window_height": 720,
                "screen_width": 1280,
                "screen_height": 720,
            })
        elif preset == "persistent_warm":
            data.update({
                "headless": False,
                "persistent_context": True,
                "enable_cache": True,
                "disable_http2": True,
                "storage_quota": 5000,
            })
        else:
            self._emit_message("Unknown browser preset")
            return
        self._emit_message(f"Preset applied: {name}")
        self.changed.emit()

    @pyqtSlot()
    def save(self) -> None:
        db_set_browser_engine(self._engine)
        db_set_camoufox_defaults(self._camoufox)
        db_set_cloakbrowser_defaults(self._cloak)
        self._emit_message("Browser settings saved")
        self.reload()

    @pyqtSlot()
    def reset(self) -> None:
        if self._engine == "cloakbrowser":
            self._cloak = dict(CLOAKBROWSER_DEFAULTS)
            db_set_cloakbrowser_defaults(self._cloak)
        else:
            self._camoufox = dict(CAMOUFOX_DEFAULTS)
            db_set_camoufox_defaults(self._camoufox)
        self._emit_message("Browser settings reset")
        self.changed.emit()
