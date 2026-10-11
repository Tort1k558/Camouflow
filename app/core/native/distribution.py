"""Immutable, checksummed Native binary installations; no profile migration."""

from contextlib import contextmanager
import hashlib
import json
import platform
import re
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from PyQt6.QtCore import QLockFile

from app.storage.db import _unsafe_windows_name

from .configuration import NativeConfiguration
from .health import probe_native_binary

MAX_ARCHIVE_BYTES = 2 * 1024 ** 3
MAX_UNPACKED_BYTES = 8 * 1024 ** 3
MAX_FILES = 50000
MARKER = {"engine": "camouflow-native-binaries", "schema": 1}


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_digest(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a lowercase SHA-256 release checksum")
    return value


def host_architecture() -> str:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        return "x64"
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    raise ValueError("Unsupported Native binary architecture")


def checked_archive_name(name: str) -> PurePosixPath:
    if not isinstance(name, str):
        raise ValueError("Unsafe Native archive path")
    path = PurePosixPath(name)
    if (not path.parts or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
            or any(_unsafe_windows_name(part) for part in path.parts)):
        raise ValueError("Unsafe Native archive path")
    return path


def archive_links_supported() -> bool:
    version = sys.version_info[:3]
    return (sys.platform != "win32" and (version >= (3, 14, 0)
            or (version[:2] == (3, 13) and version >= (3, 13, 4))
            or (version[:2] == (3, 12) and version >= (3, 12, 11))))


def resolve_native_executable(settings: dict) -> Path:
    source = settings.get("binary_source", "explicit")
    if source == "managed":
        root = settings.get("binary_store", "")
        if not isinstance(root, str) or not root.strip():
            raise ValueError("Configure an absolute Native binary store path")
        release = NativeBinaryStore(Path(root.strip())).resolve_active()
        return Path(release["executable_path"])
    if source != "explicit":
        raise ValueError("Native binary source must be explicit or managed")
    value = settings.get("executable_path", "")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Configure an explicit Native Chromium executable before launching")
    executable = Path(value.strip())
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("Native Chromium executable must be an installed absolute file")
    return executable


class NativeBinaryStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not self.root.is_absolute() or self.root != self.root.resolve():
            raise ValueError("Native binary store must be absolute and not linked")

    def _child(self, name: str) -> Path:
        path = self.root / name
        if path != path.resolve():
            raise ValueError("Native binary store paths must not be linked")
        return path

    @contextmanager
    def _locked(self):
        if self.root != self.root.resolve():
            raise ValueError("Native binary store must not be linked")
        self.root.mkdir(parents=True, exist_ok=True)
        marker = self._child("camouflow-native-binaries.json")
        lock = QLockFile(str(self._child("native-update.lock")))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise ValueError("Another process is updating Native binaries")
        try:
            if marker.exists():
                if json.loads(marker.read_text(encoding="utf-8-sig")) != MARKER:
                    raise ValueError("Incompatible Native binary store identity")
            else:
                if any(path.name != "native-update.lock" for path in self.root.iterdir()):
                    raise ValueError("Refusing to adopt an unrelated binary directory")
                marker.write_text(json.dumps(MARKER), encoding="utf-8")
            yield
        finally:
            lock.unlock()

    def inspect(self, digest: str) -> dict:
        marker = self._child("camouflow-native-binaries.json")
        if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8-sig")) != MARKER:
            raise ValueError("Native binary store identity is missing or incompatible")
        release = self._child("releases/" + checked_digest(digest))
        return self._inspect_directory(release, digest)

    def _inspect_directory(self, release: Path, digest: str) -> dict:
        metadata_path = release / "native-release.json"
        if not metadata_path.is_file() or metadata_path.is_symlink() or metadata_path.stat().st_size > 1024 * 1024:
            raise ValueError("Native release metadata is missing or unsafe")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if not isinstance(metadata, dict) or type(metadata.get("schema")) is not int or metadata["schema"] != 1:
            raise ValueError("Invalid Native release metadata")
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", str(metadata.get("native_version", ""))):
            raise ValueError("Invalid Native release version")
        if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", str(metadata.get("chromium_version", ""))):
            raise ValueError("Invalid Chromium release version")
        if metadata.get("platform") != sys.platform or metadata.get("architecture") != host_architecture():
            raise ValueError("Native release does not match this platform/architecture")
        if metadata.get("build_kind") not in {"upstream-bootstrap", "chromium-fork"}:
            raise ValueError("Native release build kind must be explicit")
        relative = checked_archive_name(metadata.get("executable", ""))
        executable = release / relative
        if not executable.resolve().is_relative_to(release) or not executable.is_file():
            raise ValueError("Native release executable is missing or outside the release")
        if sha256_file(executable) != checked_digest(metadata.get("executable_sha256")):
            raise ValueError("Native release executable checksum mismatch")
        return {**metadata, "release_sha256": digest, "executable_path": str(executable)}

    def _current(self) -> dict:
        path = self._child("current.json")
        if not path.exists():
            return {"active": None, "previous": None}
        if not path.is_file() or path.stat().st_size > 1024:
            raise ValueError("Invalid Native active release record")
        current = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(current, dict) or set(current) != {"active", "previous"}:
            raise ValueError("Invalid Native active release record")
        for digest in current.values():
            if digest is not None:
                checked_digest(digest)
        return current

    def resolve_active(self) -> dict:
        active = self._current()["active"]
        if active is None:
            raise ValueError("No managed Native binary is active")
        return self.inspect(active)

    async def activate(self, digest: str) -> dict:
        with self._locked():
            return await self._activate_locked(checked_digest(digest))

    async def rollback(self) -> dict:
        with self._locked():
            previous = self._current()["previous"]
            if previous is None:
                raise ValueError("No previous Native binary is available")
            return await self._activate_locked(previous)

    async def _activate_locked(self, digest: str) -> dict:
        release = self.inspect(digest)
        current = self._current()
        if current["active"] is not None:
            active = self.inspect(current["active"])
            if tuple(map(int, release["chromium_version"].split("."))) < tuple(map(int, active["chromium_version"].split("."))):
                raise ValueError("Chromium downgrade is blocked; existing profile compatibility has not been established")
        observed = await probe_native_binary(Path(release["executable_path"]), NativeConfiguration(), self._child("health"))
        if observed != release["chromium_version"]:
            raise ValueError("Native runtime version differs from its release manifest")
        if current["active"] == digest:
            return release
        target = self._child("current.json")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                             prefix="native-current-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"active": digest, "previous": current["active"]}, stream)
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return release

    def install_archive(self, archive: Path, expected_sha256: str) -> dict:
        digest = checked_digest(expected_sha256)
        with self._locked():
            releases = self._child("releases")
            releases.mkdir(exist_ok=True)
            target = self._child("releases/" + digest)
            if target.exists():
                return self.inspect(digest)
            with tempfile.TemporaryDirectory(prefix="native-install-", dir=self.root) as owned:
                stage = Path(owned)
                copied = stage / "bundle.tar.gz"
                hashed = hashlib.sha256()
                total = 0
                with Path(archive).open("rb") as source, copied.open("xb") as destination:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        total += len(chunk)
                        if total > MAX_ARCHIVE_BYTES:
                            raise ValueError("Native archive exceeds download size limit")
                        hashed.update(chunk)
                        destination.write(chunk)
                if hashed.hexdigest() != digest:
                    raise ValueError("Native archive checksum mismatch")
                payload = stage / "payload"
                payload.mkdir()
                names = set()
                unpacked = 0
                with tarfile.open(copied, "r:gz") as bundle:
                    for member in bundle:
                        name = checked_archive_name(member.name).as_posix().casefold()
                        if name in names:
                            raise ValueError("Duplicate/colliding Native archive entry")
                        names.add(name)
                        unpacked += member.size
                        if member.size < 0 or len(names) > MAX_FILES or unpacked > MAX_UNPACKED_BYTES:
                            raise ValueError("Native archive exceeds extraction limits")
                        if member.issparse():
                            raise ValueError("Unsupported Native archive sparse file")
                        if (member.issym() or member.islnk()) and not archive_links_supported():
                            raise ValueError("Native archive links require a patched Unix Python runtime; Windows bundles must not contain links")
                        bundle.extract(member, payload, filter="data")
                metadata = self._inspect_directory(payload, digest)
                if payload.resolve() != payload or not payload.is_relative_to(self.root) or target.resolve() != target:
                    raise ValueError("Native candidate escaped its owned store")
                payload.rename(target)
                metadata["executable_path"] = str(target / checked_archive_name(metadata["executable"]))
                return metadata
