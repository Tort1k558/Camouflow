"""Owned persistent Chromium lifecycle, independent of Camoufox and CloakBrowser."""

import asyncio
import json
from pathlib import Path

from PyQt6.QtCore import QLockFile
from playwright.async_api import async_playwright

from .configuration import NativeConfiguration
from .identity import load_or_create_identity


class NativeRuntimeError(RuntimeError):
    pass


class NativeRuntime:
    CLOSE_TIMEOUT_SECONDS = 40
    DRIVER_STOP_TIMEOUT_SECONDS = 8
    DRIVER_START_TIMEOUT_SECONDS = 30
    CONTEXT_CLOSE_TIMEOUT_SECONDS = 30

    def __init__(self, profile_dir: Path, executable: Path, configuration: NativeConfiguration):
        self.profile_dir = Path(profile_dir)
        self.executable = Path(executable)
        self.configuration = configuration
        self.context = None
        self.playwright = None
        self._profile_lock = None
        self._privacy_identity = None
        self._policy_admission = None
        self._driver_stop_task = None
        self._driver_start_task = None
        self._operation_lock = asyncio.Lock()

    @property
    def native_policy_capabilities(self) -> list[str]:
        return list(self._policy_admission.capabilities) if self._policy_admission is not None else []

    @property
    def has_resources(self) -> bool:
        return any(value is not None for value in (self.context, self.playwright, self._profile_lock,
                                                   self._driver_start_task, self._driver_stop_task))

    async def start(self, *, headless: bool = False, proxy: dict | None = None):
        async with self._operation_lock:
            if self.has_resources:
                raise NativeRuntimeError("Native profile is already running")
            admission = None
            if self.configuration.privacy_policy.required_capabilities():
                from .admission import verify_runtime_policy

                admission = await asyncio.to_thread(verify_runtime_policy, self.executable, self.configuration.privacy_policy)
            if admission is None:
                options = self.configuration.context_options()
                arguments = self.configuration.launch_arguments()
            else:
                options = self.configuration.context_options(admission=admission)
                arguments = self.configuration.launch_arguments(admission=admission)
            if not self.executable.is_file():
                raise NativeRuntimeError("Native Chromium executable is not installed")
            if not self.profile_dir.is_absolute() or self.profile_dir != self.profile_dir.resolve() or self.profile_dir.is_symlink() or self.profile_dir.is_junction():
                raise NativeRuntimeError("Native profile directory must be absolute and not a link")
            if proxy is not None and (not isinstance(proxy, dict)
                    or set(proxy) - {"server", "username", "password", "bypass"}
                    or any(not isinstance(value, str) for value in proxy.values())
                    or not proxy.get("server", "").strip()):
                raise ValueError("Invalid Native proxy configuration")
            if proxy is not None:
                proxy = dict(proxy)
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
            lock = QLockFile(str(self.profile_dir / "native-runtime.lock"))
            lock.setStaleLockTime(0)
            if not lock.tryLock(0):
                raise NativeRuntimeError("Another process owns this Native profile")
            self._profile_lock = lock
            try:
                if not marker.exists():
                    marker.write_text(json.dumps({"engine": "camouflow-native", "schema": 1}), encoding="utf-8")
                self._privacy_identity = load_or_create_identity(self.profile_dir)
                self._driver_start_task = asyncio.create_task(async_playwright().start())
                self.playwright = await asyncio.wait_for(asyncio.shield(self._driver_start_task),
                                                        timeout=self.DRIVER_START_TIMEOUT_SECONDS)
                self.context = await self.playwright.chromium.launch_persistent_context(
                    str(self.profile_dir), executable_path=str(self.executable), headless=headless,
                    chromium_sandbox=True, proxy=proxy, timeout=30000,
                    args=arguments, **options,
                )
                self._policy_admission = admission
                return self.context
            except BaseException:
                await self._close()
                raise

    async def close(self):
        async with self._operation_lock:
            await self._close()

    async def _close(self):
        if self.playwright is None and self._driver_start_task is not None:
            startup = self._driver_start_task
            if startup.done() and (startup.cancelled() or startup.exception() is not None):
                self._driver_start_task = None
            else:
                try:
                    self.playwright = await asyncio.wait_for(asyncio.shield(startup),
                                                            timeout=self.DRIVER_START_TIMEOUT_SECONDS)
                except asyncio.CancelledError:
                    if not startup.cancelled():
                        raise
                    self._driver_start_task = None
                except Exception:
                    if not startup.done() or startup.cancelled() or startup.exception() is None:
                        raise
                    self._driver_start_task = None
        context = self.context
        driver = self.playwright
        try:
            if context is not None:
                try:
                    await asyncio.wait_for(context.close(), timeout=self.CONTEXT_CLOSE_TIMEOUT_SECONDS)
                except TimeoutError as error:
                    raise TimeoutError("Native browser context close timed out") from error
        finally:
            if driver is not None:
                if self._driver_stop_task is None:
                    self._driver_stop_task = asyncio.create_task(driver.stop())
                await asyncio.wait_for(asyncio.shield(self._driver_stop_task), timeout=self.DRIVER_STOP_TIMEOUT_SECONDS)
            self.context = None
            self.playwright = None
            self._driver_stop_task = None
            self._driver_start_task = None
            self._privacy_identity = None
            self._policy_admission = None
            if self._profile_lock is not None:
                self._profile_lock.unlock()
                self._profile_lock = None
