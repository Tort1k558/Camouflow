"""Explicit Chromium capabilities without injected JavaScript fingerprint masks."""

from dataclasses import asdict, dataclass, field
import math
import re

from PyQt6.QtCore import QTimeZone

from .privacy import NativePrivacyPolicy

MEDIA_PREFERENCES = {
    "color_scheme": ("light", "dark"),
    "reduced_motion": ("no-preference", "reduce"),
    "forced_colors": ("none", "active"),
    "contrast": ("no-preference", "more"),
}


@dataclass(frozen=True)
class NativeConfiguration:
    environment: str = "desktop"
    width: int = 1366
    height: int = 768
    device_scale_factor: float = 1.0
    locale: str = "en-US"
    timezone: str = "UTC"
    permissions: tuple[str, ...] = ()
    privacy_policy: NativePrivacyPolicy = field(default_factory=NativePrivacyPolicy)
    color_scheme: str = ""
    reduced_motion: str = ""
    forced_colors: str = ""
    contrast: str = ""

    @classmethod
    def from_settings(cls, settings: dict) -> "NativeConfiguration":
        headers = settings.get("extra_http_headers", {})
        if not isinstance(headers, dict):
            raise ValueError("Native HTTP headers must be an object")
        if any(str(key).lower() in {"user-agent", "accept-language"}
               or str(key).lower().startswith("sec-ch-ua") for key in headers):
            raise ValueError("Native identity headers must not override the browser configuration")
        unsupported = {"user_agent", "platform", "platform_version", "gpu_vendor", "gpu_renderer", "webgl_vendor", "webgl_renderer", "hardware_concurrency", "device_memory", "fonts", "webrtc_ip", "fingerprint_seed", "fingerprint_noise", "screen_width", "screen_height", "launch_args", "block_webrtc", "block_webgl", "geoip", "bypass_csp", "ignore_https_errors"}
        requested = sorted(key for key in unsupported if settings.get(key))
        if requested:
            raise ValueError("Native does not support these settings: " + ", ".join(requested))
        if settings.get("persistent_context", True) is not True:
            raise ValueError("Native requires a persistent profile")
        permissions = settings.get("permissions", [])
        if not isinstance(permissions, (list, tuple)):
            raise ValueError("Native permissions must be a list")
        configuration = cls(
            environment=settings.get("environment", "desktop"),
            width=settings.get("window_width", 1366), height=settings.get("window_height", 768),
            device_scale_factor=settings.get("device_scale_factor", 1.0),
            locale=settings.get("locale", "en-US"), timezone=settings.get("timezone", "UTC"),
            **{key: settings.get(key, "") for key in MEDIA_PREFERENCES},
            permissions=tuple(permissions),
            privacy_policy=NativePrivacyPolicy.from_dict(settings.get("privacy_policy", {})),
        )
        configuration.validate()
        return configuration

    def environment_settings(self) -> dict:
        """Snapshot requested environment values, not grants, paths or key material."""
        self.validate()
        policy = {**asdict(self.privacy_policy), "fonts": list(self.privacy_policy.fonts)}
        return {
            "environment": self.environment,
            "window_width": self.width, "window_height": self.height,
            "device_scale_factor": float(self.device_scale_factor),
            "locale": self.locale, "timezone": self.timezone,
            "privacy_policy": policy,
            **{key: getattr(self, key) for key in MEDIA_PREFERENCES},
        }

    def validate(self) -> None:
        if not isinstance(self.privacy_policy, NativePrivacyPolicy):
            raise ValueError("Invalid Native privacy policy")
        self.privacy_policy.validate()
        for key, choices in MEDIA_PREFERENCES.items():
            value = getattr(self, key)
            if not isinstance(value, str) or value not in ("", *choices):
                raise ValueError("Invalid Native media preference: " + key)
        if not isinstance(self.environment, str) or self.environment not in {"desktop", "mobile_web"}:
            raise ValueError("Native supports desktop or mobile_web, not real Android/iOS")
        if any(type(value) is not int or not 240 <= value <= 8192 for value in (self.width, self.height)):
            raise ValueError("Native viewport dimensions must be integers between 240 and 8192")
        if isinstance(self.device_scale_factor, bool) or not isinstance(self.device_scale_factor, (int, float)) or not math.isfinite(self.device_scale_factor) or not 0.5 <= self.device_scale_factor <= 4:
            raise ValueError("Native device scale factor must be between 0.5 and 4")
        if not isinstance(self.locale, str) or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", self.locale):
            raise ValueError("Native locale must be a BCP47 language tag")
        if not isinstance(self.timezone, str) or not QTimeZone.isTimeZoneIdAvailable(self.timezone.encode("utf-8")):
            raise ValueError("Native timezone must be a valid IANA timezone")
        if not isinstance(self.permissions, tuple) or any(not isinstance(permission, str) or permission not in {"geolocation", "notifications", "camera", "microphone", "clipboard-read", "clipboard-write"} for permission in self.permissions):
            raise ValueError("Unsupported Native browser permission")

    def context_options(self, *, admission=None) -> dict:
        self.validate()
        self.privacy_policy.require_verified_runtime(admission)
        mobile = self.environment == "mobile_web"
        return {
            "viewport": {"width": self.width, "height": self.height},
            "screen": {"width": self.width, "height": self.height},
            "device_scale_factor": float(self.device_scale_factor),
            "locale": self.locale,
            "timezone_id": self.timezone,
            "is_mobile": mobile,
            "has_touch": mobile,
            "permissions": list(self.permissions),
            **{key: getattr(self, key) for key in MEDIA_PREFERENCES if getattr(self, key)},
        }

    def launch_arguments(self, *, admission=None) -> list[str]:
        self.validate()
        self.privacy_policy.require_verified_runtime(admission)
        return ["--lang=" + self.locale, "--accept-lang=" + self.locale, *self.privacy_policy.prepared_arguments()]

    def limitations(self) -> list[str]:
        notes = (["Experimental source-level controls requested; activation requires a reviewed local runtime. Not general anti-bot invisibility."]
                 if self.privacy_policy.required_capabilities() else
                 ["Chromium fingerprint APIs retain their native values; Canvas/WebGL/Audio/fonts/hardware are not masked."])
        if self.environment == "mobile_web":
            notes.append("Mobile Web is desktop Chromium with viewport/touch emulation, not an Android Chrome or iOS Safari identity.")
        return notes
