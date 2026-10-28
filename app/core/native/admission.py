"""Experimental controls for reviewed local bundles, not signed online updates."""

from dataclasses import dataclass
from pathlib import Path
import sys

from .privacy import NativePrivacyPolicy

# Reviewed package bytes, not a claim made by an editable release manifest.
_REVIEWED_PACKAGES = {
    "84e8d2369be630825afbff2732b09d5d81bb699e3c60025b73756c3fc305c10a": {
        "manifest_sha256": "465b32ab5ad0488543ac3d9410e3f8576faa621e87399fa1d5db9959b5c0ed27",
        "platform": "win32",
        "capabilities": ("hardware", "fonts", "webrtc", "automation", "identity", "font-rasterization", "text-rendering"),
    },
}


@dataclass(frozen=True)
class NativePolicyAdmission:
    executable: Path
    release_sha256: str
    policy: NativePrivacyPolicy
    capabilities: tuple[str, ...]

    def require_policy(self, policy: NativePrivacyPolicy) -> None:
        reviewed = _REVIEWED_PACKAGES.get(self.release_sha256)
        if (reviewed is None or reviewed["platform"] != sys.platform or self.policy != policy
                or self.capabilities != tuple(policy.required_capabilities())
                or not set(self.capabilities).issubset(reviewed["capabilities"])):
            raise ValueError("Native policy differs from its verified runtime admission")


def verify_runtime_policy(executable: Path, policy: NativePrivacyPolicy) -> NativePolicyAdmission:
    from .distribution import NativeBinaryStore, sha256_file

    policy.validate()
    requested = tuple(policy.required_capabilities())
    executable = Path(executable)
    reviewed = _REVIEWED_PACKAGES.get(executable.parent.name)
    if (not requested or reviewed is None or reviewed["platform"] != sys.platform
            or executable.name != "chrome.exe" or executable.parent.parent.name != "releases"
            or not executable.is_absolute() or executable != executable.resolve()):
        raise ValueError("Native privacy controls require a verified reviewed managed package")
    if not set(requested).issubset(reviewed["capabilities"]):
        raise ValueError("Requested Native capabilities are not verified for this package")
    manifest = executable.parent / "native-release.json"
    if (manifest != manifest.resolve() or not manifest.is_file() or manifest.stat().st_size > 1024 * 1024
            or sha256_file(manifest) != reviewed["manifest_sha256"]):
        raise ValueError("Native release manifest differs from the verified package")
    store = NativeBinaryStore(executable.parent.parent.parent)
    release = store.inspect(executable.parent.name)
    if (Path(release["executable_path"]) != executable or release["build_kind"] != "chromium-fork"
            or sha256_file(manifest) != reviewed["manifest_sha256"]):
        raise ValueError("Native release changed during verified policy admission")
    admission = NativePolicyAdmission(executable, release["release_sha256"], policy, requested)
    admission.require_policy(policy)
    return admission
