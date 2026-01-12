"""Thread-safe scenario debugging controls used during execution."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event, Lock
from typing import Callable, Optional


@dataclass(frozen=True)
class ScenarioDebugUpdate:
    scenario_name: str
    account_name: str
    step_index: int
    total_steps: int
    action: str
    description: str
    tag: str
    reloaded_at: Optional[float] = None


@dataclass(frozen=True)
class ScenarioDebugDecision:
    stop: bool = False
    jump_to_index: Optional[int] = None
    jump_to_tag: Optional[str] = None


class ScenarioDebugSession:
    """
    Thread-safe controller shared between UI and the scenario engine.

    Notes:
    - Pause/stop/jump are cooperative and are applied between steps.
    - Updates may be forwarded to UI via an injected dispatcher.
    """

    def __init__(
        self,
        *,
        ui_invoke: Optional[Callable[[Callable[[], None]], None]] = None,
        on_update: Optional[Callable[[ScenarioDebugUpdate], None]] = None,
        on_browser_closed: Optional[Callable[[], None]] = None,
        on_finished: Optional[Callable[[bool, Optional[str]], None]] = None,
    ) -> None:
        self._enabled = True
        self._run_event = Event()
        self._run_event.set()
        self._stop_event = Event()
        self._lock = Lock()
        self._jump_to_index: Optional[int] = None
        self._jump_to_tag: Optional[str] = None
        self._initial_index: Optional[int] = None
        self._current_account_name: str = ""
        self._ui_invoke = ui_invoke
        self._on_update = on_update
        self._on_browser_closed = on_browser_closed
        self._on_finished = on_finished
        self._last_reload_at: Optional[float] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def paused(self) -> bool:
        return self._enabled and not self._run_event.is_set()

    def disable(self) -> None:
        self._enabled = False
        self._run_event.set()

    def pause(self) -> None:
        if self._enabled:
            self._run_event.clear()

    def resume(self) -> None:
        self._run_event.set()

    def request_stop(self) -> None:
        self._stop_event.set()
        self._run_event.set()

    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def notify_finished(self, ok: bool, reason: Optional[str] = None) -> None:
        if not self._on_finished:
            return
        payload_ok = bool(ok)
        payload_reason = None if reason is None else str(reason)
        if self._ui_invoke:
            self._ui_invoke(lambda: self._on_finished(payload_ok, payload_reason))
        else:
            self._on_finished(payload_ok, payload_reason)

    def notify_browser_closed(self) -> None:
        """
        Called when the underlying browser window/process is closed.
        Safe to call from any thread.
        """
        self._stop_event.set()
        self._run_event.set()
        if not self._on_browser_closed:
            return
        if self._ui_invoke:
            self._ui_invoke(self._on_browser_closed)
        else:
            self._on_browser_closed()

    def wait_for_command(self) -> ScenarioDebugDecision:
        """
        Block until a new jump command arrives or stop is requested.

        Intended to be called from a worker thread (not the Qt/UI thread).
        """
        while True:
            if self._stop_event.is_set():
                return ScenarioDebugDecision(stop=True)
            self._run_event.wait()
            if self._stop_event.is_set():
                return ScenarioDebugDecision(stop=True)
            decision = self.consume_jump()
            if decision.jump_to_index is not None or decision.jump_to_tag:
                return decision
            # If user pressed Resume without selecting a step, re-pause and continue waiting.
            self.pause()

    def notify_browser_closed_for(self, account_name: str) -> None:
        """
        Notify browser closure for a specific account/profile.

        If a different account is currently being debugged, the notification is ignored.
        """
        candidate = str(account_name or "")
        with self._lock:
            current = self._current_account_name
        if current and candidate and current != candidate:
            return
        self.notify_browser_closed()

    def set_initial_step(self, step_one_based: int) -> None:
        try:
            idx = int(step_one_based) - 1
        except Exception:
            return
        if idx < 0:
            idx = 0
        with self._lock:
            self._initial_index = idx

    def consume_initial_step(self) -> Optional[int]:
        with self._lock:
            idx = self._initial_index
            self._initial_index = None
            return idx

    def request_jump_to_step(self, step_one_based: int) -> None:
        try:
            idx = int(step_one_based) - 1
        except Exception:
            return
        if idx < 0:
            idx = 0
        with self._lock:
            self._jump_to_index = idx
            self._jump_to_tag = None
        self._run_event.set()

    def request_jump_to_tag(self, tag: str) -> None:
        tag = str(tag or "").strip()
        if not tag:
            return
        with self._lock:
            self._jump_to_tag = tag
            self._jump_to_index = None
        self._run_event.set()

    def consume_jump(self) -> ScenarioDebugDecision:
        with self._lock:
            idx = self._jump_to_index
            tag = self._jump_to_tag
            self._jump_to_index = None
            self._jump_to_tag = None
        if idx is not None:
            return ScenarioDebugDecision(jump_to_index=idx)
        if tag is not None:
            return ScenarioDebugDecision(jump_to_tag=tag)
        return ScenarioDebugDecision()

    def notify_reload(self) -> None:
        self._last_reload_at = time.time()

    def last_reload_at(self) -> Optional[float]:
        return self._last_reload_at

    def before_step(
        self,
        *,
        scenario_name: str,
        account_name: str,
        step_index: int,
        total_steps: int,
        action: str,
        description: str,
        tag: str,
    ) -> ScenarioDebugDecision:
        if not self._enabled:
            return ScenarioDebugDecision()

        update = ScenarioDebugUpdate(
            scenario_name=str(scenario_name or ""),
            account_name=str(account_name or ""),
            step_index=int(step_index),
            total_steps=int(total_steps),
            action=str(action or ""),
            description=str(description or ""),
            tag=str(tag or ""),
            reloaded_at=self._last_reload_at,
        )
        with self._lock:
            self._current_account_name = update.account_name
        if self._on_update:
            if self._ui_invoke:
                self._ui_invoke(lambda: self._on_update(update))
            else:
                self._on_update(update)

        self._run_event.wait()
        if self._stop_event.is_set():
            return ScenarioDebugDecision(stop=True)
        return self.consume_jump()
