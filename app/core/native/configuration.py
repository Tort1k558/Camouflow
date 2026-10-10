"""Explicit Chromium capabilities without injected JavaScript fingerprint masks."""

from dataclasses import dataclass
import math
import re

from PyQt6.QtCore import QTimeZone


@dataclass(frozen=True)
class NativeConfiguration:
    environment: str = "desktop"
    width: int = 1366
    height: int = 768
    device_scale_factor: float = 1.0
    locale: str = "en-US"
    timezone: str = "UTC"
    permissions: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.environment not in {"desktop", "mobile_web"}:
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

    def context_options(self) -> dict:
        self.validate()
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
        }

    def limitations(self) -> list[str]:
        notes = ["Chromium fingerprint APIs retain their native values; Canvas/WebGL/Audio/fonts/hardware are not masked."]
        if self.environment == "mobile_web":
            notes.append("Mobile Web is desktop Chromium with viewport/touch emulation, not an Android Chrome or iOS Safari identity.")
        return notes
