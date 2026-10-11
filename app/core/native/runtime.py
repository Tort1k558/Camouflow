"""Owned persistent Chromium lifecycle, independent of Camoufox and CloakBrowser."""

import asyncio
import json
from pathlib import Path

from PyQt6.QtCore import QLockFile
from playwright.async_api import async_playwright

from .configuration import NativeConfiguration


class NativeRuntimeError(RuntimeError):
    pass


class NativeRuntime:
    CLOSE_TIMEOUT_SECONDS = 40

    def __init__(self, profile_dir: Path, executable: Path, configuration: NativeConfiguration):
        self.profile_dir = Path(profile_dir)
        self.executable = Path(executable)
        self.configuration = configuration
        self.context = None
        self.playwright = None
        self._profile_lock = None
        self._operation_lock = asyncio.Lock()

    async def start(self, *, headless: bool = False, proxy: dict | None = None):
        async with self._operation_lock:
            if self.context is not None or self.playwright is not None:
                raise NativeRuntimeError("Native profile is already running")
            options = self.configuration.context_options()
            if not self.executable.is_file():
                raise NativeRuntimeError("Native Chromium executable is not installed")
            if not self.profile_dir.is_absolute() or self.profile_dir != self.profile_dir.resolve() or self.profile_dir.is_symlink() or self.profile_dir.is_junction():
                raise NativeRuntimeError("Native profile directory must be absolute and not a link")
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            marker = self.profile_dir / "camouflow-native.json"
            if marker.is_symlink() or (self.profile_dir / "native-runtime.lock").is_symlink():
                raise NativeRuntimeError("Native profile metadata must not be linked")
            if not marker.exists() and any(path.name != "native-runtime.lock" for path in self.profile_dir.iterdir()):
                raise NativeRuntimeError("Native requires its own empty profile directory, not an existing browser profile")
            if marker.exists():
                try:
                    identity = json.loads(marker.read_text(encoding="utf-8-sig"))
                except (OSError, ValueError):
                    raise NativeRuntimeError("Native profile identity is invalid") from None
                if identity != {"engine": "camouflow-native", "schema": 1}:
                    raise NativeRuntimeError("Native profile identity is incompatible")
            if proxy is not None and (not isinstance(proxy, dict) or not proxy.get("server") or set(proxy) - {"server", "username", "password", "bypass"}):
                raise ValueError("Invalid Native proxy configuration")
            lock = QLockFile(str(self.profile_dir / "native-runtime.lock"))
            lock.setStaleLockTime(0)
            if not lock.tryLock(0):
                raise NativeRuntimeError("Another process owns this Native profile")
            self._profile_lock = lock
            try:
                if not marker.exists():
                    marker.write_text(json.dumps({"engine": "camouflow-native", "schema": 1}), encoding="utf-8")
                self.playwright = await async_playwright().start()
                self.context = await self.playwright.chromium.launch_persistent_context(
                    str(self.profile_dir), executable_path=str(self.executable), headless=headless,
                    chromium_sandbox=True, proxy=proxy, timeout=30000,
                    args=self.configuration.launch_arguments(), **options,
                )
                return self.context
            except BaseException:
                await self._close()
                raise

    async def close(self):
        async with self._operation_lock:
            await self._close()

    async def _close(self):
        context = self.context
        driver = self.playwright
        try:
            if context is not None:
                await asyncio.wait_for(context.close(), timeout=30)
        finally:
            if driver is not None:
                await asyncio.wait_for(driver.stop(), timeout=8)
            self.context = None
            self.playwright = None
            if self._profile_lock is not None:
                self._profile_lock.unlock()
                self._profile_lock = None
