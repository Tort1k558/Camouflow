"""Validated Native privacy policy drafts; no unverified runtime activation."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class NativePrivacyPolicy:
    cpu_limit: int = 0
    memory_limit: float = 0
    fonts: tuple[str, ...] = ()
    restrict_webrtc: bool = False
    conceal_automation: bool = False
    native_user_agent: bool = False

    @classmethod
    def from_dict(cls, value: dict) -> "NativePrivacyPolicy":
        if not isinstance(value, dict) or set(value) - set(cls.__dataclass_fields__):
            raise ValueError("Unknown or invalid Native privacy policy fields")
        fonts = value.get("fonts", [])
        if not isinstance(fonts, (list, tuple)):
            raise ValueError("Native font families must be a list")
        policy = cls(**{**value, "fonts": tuple(fonts)})
        policy.validate()
        return policy

    def validate(self) -> None:
        if type(self.cpu_limit) is not int or not 0 <= self.cpu_limit <= 64:
            raise ValueError("Native CPU limit must be 0 (native) or 1..64")
        if (isinstance(self.memory_limit, bool) or not isinstance(self.memory_limit, (int, float))
                or not math.isfinite(self.memory_limit) or self.memory_limit not in {0, .25, .5, 1, 2, 4, 8, 16}):
            raise ValueError("Native memory limit must be 0 (native), 0.25, 0.5, 1, 2, 4, 8 or 16 GiB")
        if any(type(value) is not bool for value in (self.restrict_webrtc, self.conceal_automation, self.native_user_agent)):
            raise ValueError("Native privacy switches must be booleans")
        if not isinstance(self.fonts, tuple) or len(self.fonts) > 64:
            raise ValueError("Native font selection permits at most 64 families")
        if self.fonts:
            keys = set()
            for name in self.fonts:
                if (not isinstance(name, str) or not 1 <= len(name) <= 128 or name != name.strip()
                        or any(ord(c) < 32 or ord(c) > 126 or c in ',"\\;' for c in name)
                        or name.lower() in keys):
                    raise ValueError("Native font names must be unique printable ASCII families")
                keys.add(name.lower())
            if "arial" not in keys or len(",".join(self.fonts)) > 4096:
                raise ValueError("Native font selection requires Arial and at most 4096 CSV bytes")

    def required_capabilities(self) -> list[str]:
        self.validate()
        return [name for name, requested in (
            ("hardware", bool(self.cpu_limit or self.memory_limit)), ("fonts", bool(self.fonts)),
            ("webrtc", self.restrict_webrtc), ("automation", self.conceal_automation),
            ("identity", self.native_user_agent)) if requested]

    def prepared_arguments(self) -> list[str]:
        self.validate()
        arguments = []
        if self.cpu_limit:
            arguments.append(f"--camouflow-hardware-concurrency={self.cpu_limit}")
        if self.memory_limit:
            arguments.append(f"--camouflow-device-memory={self.memory_limit:g}")
        if self.fonts:
            arguments.append("--camouflow-font-families=" + ",".join(self.fonts))
        if self.restrict_webrtc:
            arguments.append("--camouflow-webrtc-ip-handling-policy=disable_non_proxied_udp")
        if self.conceal_automation:
            arguments.append("--enable-blink-features=CamouFlowAutomationConcealed")
        if self.native_user_agent:
            arguments.append("--camouflow-native-user-agent")
        return arguments

    def require_verified_runtime(self) -> None:
        requested = self.required_capabilities()
        if requested:
            raise ValueError("Native privacy policy is saved but cannot run until own-fork capabilities are verified: " + ", ".join(requested))
