import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class BrowserLifecycleManager:
    """Browser close/ready/process-exit callbacks and process watchdog."""

    def __init__(
        self,
        profile_name: str,
        user_data_dir_provider: Callable[[], Path],
        browser_provider: Callable[[], object],
        context_provider: Callable[[], object],
        page_provider: Callable[[], object],
        logger,
    ) -> None:
        self.profile_name = profile_name
        self._user_data_dir_provider = user_data_dir_provider
        self._browser_provider = browser_provider
        self._context_provider = context_provider
        self._page_provider = page_provider
        self.logger = logger

        self._close_callbacks: List[Callable[[], None]] = []
        self._closed_notified = False
        self._process_exit_callbacks: List[Callable[[], None]] = []
        self._process_exited_notified = False
        self._close_listener_attached = False
        self._ready_callbacks: List[Callable[[], None]] = []
        self._ready_notified = False
        self._process_watchdog_started = False
        self._resource_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        try:
            self._memory_limit_mb = max(0, int(os.environ.get("CAMOUFLOW_PROFILE_MEMORY_LIMIT_MB", "1536") or 0))
        except ValueError:
            self._memory_limit_mb = 1536

    def reset_for_start(self) -> None:
        self._closed_notified = False
        self._process_exited_notified = False
        self._close_listener_attached = False

    def reset_ready(self) -> None:
        self._ready_notified = False

    def has_process_exit_callbacks(self) -> bool:
        return bool(self._process_exit_callbacks)

    def add_process_exit_callback(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            return
        if self._process_exited_notified:
            try:
                callback()
            except Exception:
                pass
            return
        self._process_exit_callbacks.append(callback)
        if self._browser_provider() is not None or self._context_provider() is not None:
            self.start_process_watchdog()

    def add_close_callback(self, callback: Callable[[], None]) -> None:
        if not callable(callback):
            return
        if self._closed_notified:
            try:
                callback()
            except Exception:
                pass
            return
        self._close_callbacks.append(callback)

    def add_resource_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        if callable(callback):
            self._resource_callbacks.append(callback)
            self.start_process_watchdog()

    def notify_resource(self, resource: Dict[str, Any]) -> None:
        for callback in list(self._resource_callbacks):
            try:
                callback(resource)
            except Exception:
                continue

    def add_ready_callback(self, callback: Callable[[], None]) -> None:
        if callable(callback):
            if self._ready_notified:
                try:
                    callback()
                except Exception:
                    pass
            else:
                self._ready_callbacks.append(callback)

    def notify_browser_closed(self) -> None:
        if self._closed_notified:
            return
        self._closed_notified = True
        try:
            self.logger.info("Browser closed detected for %s", self.profile_name)
        except Exception:
            pass
        for callback in list(self._close_callbacks):
            try:
                callback()
            except Exception:
                continue

    def notify_process_exited(self) -> None:
        if self._process_exited_notified:
            return
        self._process_exited_notified = True
        for callback in list(self._process_exit_callbacks):
            try:
                callback()
            except Exception:
                continue

    def notify_browser_ready(self) -> None:
        if self._ready_notified:
            return
        self._ready_notified = True
        for callback in list(self._ready_callbacks):
            try:
                callback()
            except Exception:
                continue
        self._ready_callbacks.clear()

    def attach_close_listeners(self) -> None:
        if self._close_listener_attached:
            return

        def _safe_attach(target, event: str) -> None:
            if not target:
                return
            handler = getattr(target, "on", None)
            if callable(handler):
                try:
                    target.on(event, lambda *_args, **_kwargs: self.notify_browser_closed())
                except Exception:
                    pass

        _safe_attach(self._browser_provider(), "disconnected")
        _safe_attach(self._context_provider(), "close")
        page = self._page_provider()
        if page is not None:
            try:
                page.on("close", lambda *_args, **_kwargs: self.notify_browser_closed())
            except Exception:
                pass
        self._close_listener_attached = True

    def start_process_watchdog(self) -> None:
        """
        Best-effort watchdog that fires process-exit callbacks when the browser window/process exits.

        Uses a Windows process lookup by profile directory when possible. Falls back to no-op on other platforms.
        """
        if self._process_watchdog_started:
            return
        self._process_watchdog_started = True

        def worker() -> None:
            if not sys.platform.startswith("win"):
                return

            env = dict(os.environ)
            env["_CAMOUFLOW_PROFILE_DIR"] = str(self._user_data_dir_provider())
            ps_exists = (
                "$target=$env:_CAMOUFLOW_PROFILE_DIR; "
                "$rx=[regex]::Escape($target); "
                "$ps=@(Get-CimInstance Win32_Process | Where-Object { "
                "  $_.CommandLine -and $_.CommandLine -match $rx -and "
                "  $_.Name -notin @('node.exe','python.exe','pythonw.exe','powershell.exe') "
                "}); $p=$ps | Select-Object -First 1; "
                "if($p){\"$($p.ProcessId)|$($p.WorkingSetSize)|$($ps.Count)\"} else {'0'}"
            )

            seen = False
            while not self._process_exited_notified:
                try:
                    out = subprocess.check_output(
                        ["powershell", "-NoProfile", "-Command", ps_exists],
                        env=env,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                    )
                    value = (out or "").strip()
                    exists = value != "0" and "|" in value
                    if exists:
                        pid_text, memory_text, count_text = value.split("|", 2)
                        memory_bytes = int(memory_text or 0)
                        memory_mb = round(memory_bytes / (1024 * 1024), 1)
                        resource = {
                            "pid": int(pid_text or 0),
                            "memory_mb": memory_mb,
                            "memory_limit_mb": self._memory_limit_mb,
                            "over_limit": bool(self._memory_limit_mb and memory_mb > self._memory_limit_mb),
                            "profile_processes": int(count_text or 1),
                            "zombie_suspected": int(count_text or 1) > 1,
                        }
                        self.notify_resource(resource)
                        if resource["over_limit"]:
                            self.logger.warning(
                                "Stopping browser for %s: %.1f MB exceeds %s MB",
                                self.profile_name, memory_mb, self._memory_limit_mb,
                            )
                            subprocess.run(
                                ["taskkill", "/PID", str(resource["pid"]), "/T", "/F"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=False,
                            )
                except Exception:
                    exists = False

                if exists:
                    seen = True
                elif seen:
                    break

                time.sleep(1.0)

            if not seen:
                return
            self.notify_process_exited()
            self.notify_browser_closed()

        threading.Thread(target=worker, daemon=True).start()
