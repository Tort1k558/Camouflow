"""Local profile keys for future native privacy policy; never browser switches."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import secrets

from PyQt6.QtCore import QFileDevice, QIODevice, QSaveFile


IDENTITY_FILE = "camouflow-native-privacy.json"


@dataclass(frozen=True)
class NativePrivacyIdentity:
    seed: bytes = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.seed, bytes) or len(self.seed) != 32:
            raise ValueError("Native privacy identity requires a 256-bit key")


def load_or_create_identity(profile: Path) -> NativePrivacyIdentity:
    """Call only while owning the Native runtime's exclusive profile lock."""
    if (not profile.is_absolute() or profile != profile.resolve() or not profile.is_dir()
            or profile.is_symlink() or profile.is_junction()):
        raise ValueError("Native privacy identity requires owned canonical profile storage")
    path = profile / IDENTITY_FILE
    if path.is_symlink() or path.is_junction():
        raise ValueError("Native privacy identity must not be linked")
    if path.exists():
        if not path.is_file() or path.stat().st_size > 256:
            raise ValueError("Native privacy identity is invalid")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(payload, dict) or set(payload) != {"schema", "seed"}
                    or type(payload["schema"]) is not int or payload["schema"] != 1
                    or not isinstance(payload["seed"], str) or len(payload["seed"]) != 64
                    or any(c not in "0123456789abcdef" for c in payload["seed"])):
                raise ValueError
            return NativePrivacyIdentity(bytes.fromhex(payload["seed"]))
        except (UnicodeError, ValueError):
            raise ValueError("Native privacy identity is invalid; it was not regenerated") from None
    identity = NativePrivacyIdentity(secrets.token_bytes(32))
    payload = json.dumps({"schema": 1, "seed": identity.seed.hex()}).encode("utf-8")
    destination = QSaveFile(str(path))
    destination.setDirectWriteFallback(False)
    if not destination.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError("Cannot atomically create Native privacy identity")
    try:
        if not destination.setPermissions(QFileDevice.Permission.ReadOwner | QFileDevice.Permission.WriteOwner):
            raise OSError("Cannot set Native privacy identity file permissions")
        if destination.write(payload) != len(payload) or not destination.commit():
            raise OSError("Cannot persist Native privacy identity")
    except BaseException:
        destination.cancelWriting()
        raise
    return identity
