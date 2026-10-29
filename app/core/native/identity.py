"""Local profile keys and native derivation references; never browser switches."""

import hashlib
import hmac
import json
import os
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QFile, QFileDevice, QIODevice, QSaveFile

IDENTITY_FILE = "camouflow-native-privacy.json"


def _require_windows_acls(directory: Path) -> None:
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetVolumePathNameW.restype = wintypes.BOOL
    kernel.GetVolumeInformationW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetVolumeInformationW.restype = wintypes.BOOL
    volume = ctypes.create_unicode_buffer(32768)
    flags = wintypes.DWORD()
    if not kernel.GetVolumePathNameW(str(directory), volume, len(volume)):
        raise OSError("Cannot inspect Native identity filesystem ACL support")
    if not kernel.GetVolumeInformationW(volume.value, None, 0, None, None, ctypes.byref(flags), None, 0):
        raise OSError("Cannot inspect Native identity filesystem ACL support")
    if not flags.value & 0x00000008:  # FILE_PERSISTENT_ACLS
        raise OSError("Native privacy identity requires a filesystem with persistent ACLs")


def _save_windows_identity(path: Path, payload: bytes, *, replace: bool) -> None:
    _require_windows_acls(path.parent)
    temporary = path.with_name("." + IDENTITY_FILE + "." + secrets.token_hex(16) + ".tmp")
    destination = QFile(str(temporary))
    permissions = QFileDevice.Permission.ReadOwner | QFileDevice.Permission.WriteOwner
    # QSaveFile.setPermissions does not restrict Windows ACLs; creation permissions do.
    if not destination.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.NewOnly, permissions):
        raise OSError("Cannot privately create Native privacy identity")
    try:
        if destination.write(payload) != len(payload) or not destination.flush():
            raise OSError("Cannot persist Native privacy identity")
        os.fsync(destination.handle())
        destination.close()
        if replace:
            os.replace(temporary, path)
        else:
            os.rename(temporary, path)
    finally:
        destination.close()
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class NativePrivacyIdentity:
    seed: bytes = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.seed, bytes) or len(self.seed) != 32:
            raise ValueError("Native privacy identity requires a 256-bit key")

    def derive(self, partition_key: bytes, surface: str) -> bytes:
        """Accept a trusted serialized browser storage partition, never a URL guess."""
        label = self._surface_label(partition_key, surface)
        message = (b"CamouFlowNative/privacy/v1\0" + len(label).to_bytes(4, "big") + label
                   + len(partition_key).to_bytes(4, "big") + partition_key)
        return hmac.digest(self.seed, message, hashlib.sha256)

    def derive_profile_identity(self, partition_key: bytes, surface: str) -> bytes:
        """Reference stable profile entropy; does not authorize a partition or enable a mode."""
        label = self._surface_label(partition_key, surface)
        message = b"Glint/profile-identity/v1\0" + len(label).to_bytes(4, "big") + label
        return hmac.digest(self.seed, message, hashlib.sha256)

    @staticmethod
    def _surface_label(partition_key: bytes, surface: str) -> bytes:
        if not isinstance(partition_key, bytes) or not 1 <= len(partition_key) <= 8192:
            raise ValueError("Native privacy derivation requires a bounded browser partition")
        if not isinstance(surface, str) or surface not in {"canvas", "webgl", "webgpu", "audio"}:
            raise ValueError("Unknown Native privacy surface")
        return surface.encode("ascii")


def load_or_create_identity(profile: Path) -> NativePrivacyIdentity:
    """Call only while owning the Native runtime's exclusive profile lock."""
    if (not profile.is_absolute() or profile != profile.resolve() or not profile.is_dir()
            or profile.is_symlink() or profile.is_junction()):
        raise ValueError("Native privacy identity requires owned canonical profile storage")
    path = profile / IDENTITY_FILE
    if path.is_symlink() or path.is_junction():
        raise ValueError("Native privacy identity must not be linked")
    if path.exists():
        metadata = path.stat()
        if not path.is_file() or metadata.st_size > 256:
            raise ValueError("Native privacy identity is invalid")
        if metadata.st_nlink != 1:
            raise ValueError("Native privacy identity must not be hard linked")
        try:
            with path.open("rb") as source:
                original = source.read(257)
            if len(original) > 256:
                raise ValueError
            payload = json.loads(original.decode("utf-8"))
            if (not isinstance(payload, dict) or set(payload) != {"schema", "seed"}
                    or type(payload["schema"]) is not int or payload["schema"] != 1
                    or not isinstance(payload["seed"], str) or len(payload["seed"]) != 64
                    or any(c not in "0123456789abcdef" for c in payload["seed"])):
                raise ValueError
            identity = NativePrivacyIdentity(bytes.fromhex(payload["seed"]))
        except (UnicodeError, ValueError):
            raise ValueError("Native privacy identity is invalid; it was not regenerated") from None
        if sys.platform == "win32":
            _save_windows_identity(path, original, replace=True)
        return identity
    identity = NativePrivacyIdentity(secrets.token_bytes(32))
    payload = json.dumps({"schema": 1, "seed": identity.seed.hex()}).encode("utf-8")
    if sys.platform == "win32":
        _save_windows_identity(path, payload, replace=False)
        return identity
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
