import asyncio
import datetime
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

import json
from pathlib import Path

from app.core.browser_interface import BrowserInterface
from app.core.shared_vars import SharedVarsManager
from app.storage.db import (
    Scenario,
    PROJECT_ROOT,
    db_get_scenario_path,
    db_get_setting,
    db_set_setting,
    profile_dir_for_email,
)
from app.services.scenario_debug import ScenarioDebugSession
from app.services.steps.base import StepResult
from app.services.steps.data import DataSteps
from app.services.steps.flow import FlowSteps
from app.services.steps.helpers import LocatorSteps, TemplateSteps
from app.services.steps.interaction import InteractionSteps
from app.services.steps.navigation import NavigationSteps
from app.services.steps.shared import SharedSteps


class ScenarioExecutor(
    NavigationSteps,
    InteractionSteps,
    DataSteps,
    SharedSteps,
    FlowSteps,
    TemplateSteps,
    LocatorSteps,
    BrowserInterface,
):
    """
    Executes a declarative scenario (list of steps) using Playwright through BrowserInterface.
    Supports variables, iframe work, branching and tab management.
    """

    def __init__(
        self,
        account_payload: Dict,
        proxy: str,
        scenario: Scenario,
        keep_browser_open: bool = True,
        shared_variables: Optional[Dict[str, str]] = None,
        debug_session: Optional[ScenarioDebugSession] = None,
        scenario_path: Optional[Path] = None,
    ) -> None:
        profile_name = str(account_payload.get("name"))
        camoufox_settings = account_payload.get("_camoufox_settings") or account_payload.get("camoufox_settings")
        super().__init__(
            profile_name=profile_name,
            proxy=proxy,
            keep_browser_open=keep_browser_open,
            camoufox_settings=camoufox_settings,
        )
        self.scenario = scenario
        self.debug_session = debug_session
        self._scenario_path = scenario_path
        self._debug_mtimes: Dict[str, float] = {}
        base_name = getattr(self.scenario, "name", None)
        self._scenario_stack: List[str] = [str(base_name)] if base_name else []
        self.variables: Dict[str, str] = {}
        # Keep a reference to shared variables via manager so actions mutate common store.
        self.shared_manager = SharedVarsManager.instance()
        if shared_variables is not None:
            self.shared_manager.set_store(shared_variables)
        self.shared_vars: Dict[str, object] = self.shared_manager.all()
        payload = dict(account_payload or {})
        self.account_payload = payload
        for key, val in payload.items():
            if key == "extra_fields" and isinstance(val, dict):
                for ek, ev in val.items():
                    self.variables[str(ek)] = "" if ev is None else str(ev)
            else:
                self.variables[str(key)] = "" if val is None else str(val)
        if shared_variables:
            self.variables.update(shared_variables)
        self.variables.setdefault("cookies", "[]")
        self.variables.setdefault("timestamp", "")
        self._profile_vars_path = Path(profile_dir_for_email(profile_name)) / "scenario_vars.json"

    @staticmethod
    def _contains_cookies_template(value: object) -> bool:
        if isinstance(value, str):
            lowered = value.lower()
            return "{{" in lowered and "cookies" in lowered
        if isinstance(value, dict):
            return any(ScenarioExecutor._contains_cookies_template(v) for v in value.values())
        if isinstance(value, list):
            return any(ScenarioExecutor._contains_cookies_template(v) for v in value)
        return False

    @staticmethod
    def _contains_timestamp_template(value: object) -> bool:
        if isinstance(value, str):
            lowered = value.lower()
            return "{{" in lowered and "timestamp" in lowered
        if isinstance(value, dict):
            return any(ScenarioExecutor._contains_timestamp_template(v) for v in value.values())
        if isinstance(value, list):
            return any(ScenarioExecutor._contains_timestamp_template(v) for v in value)
        return False

    async def _update_cookies_variable(self) -> None:
        ctx = getattr(self, "context", None)
        if ctx is None:
            self.variables["cookies"] = "[]"
            return

        cookies: List[Dict[str, object]] = []
        seen_keys: set[Tuple[str, str, str]] = set()

        def _add_cookie_list(items: object) -> None:
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                domain = str(item.get("domain") or item.get("host") or item.get("host_key") or "")
                name = str(item.get("name") or "")
                path = str(item.get("path") or "/")
                key = (domain, name, path)
                if not domain or not name or key in seen_keys:
                    continue
                seen_keys.add(key)
                cookies.append(item)

        # Prefer Playwright's storage_state cookies when available.
        try:
            state = await ctx.storage_state()
            if isinstance(state, dict):
                _add_cookie_list(state.get("cookies"))
        except Exception as exc:
            self.logger.debug("Failed to read cookies via storage_state: %s", exc)

        # Also include cookies() output (may differ by implementation).
        try:
            raw = await ctx.cookies()
            _add_cookie_list(raw)
        except Exception as exc:
            self.logger.debug("Failed to read cookies via context.cookies(): %s", exc)

        # Fallback to on-disk DBs (same approach as Profile settings) to include persisted cookies.
        _add_cookie_list(self._read_profile_cookies_fallback())

        try:
            self.variables["cookies"] = json.dumps(cookies or [], ensure_ascii=False, separators=(",", ":"))
        except Exception:
            self.variables["cookies"] = "[]"

    def _read_profile_cookies_fallback(self) -> List[Dict[str, object]]:
        """
        Read cookies directly from profile storage (best-effort).

        This matches the approach used in Profile settings: scan for Firefox and Chromium cookie DBs and
        read them in read-only mode (copying to a temp file if locked).
        """
        import os
        import shutil
        import sqlite3
        import tempfile

        profile_dir = Path(profile_dir_for_email(self.profile_name))
        if not profile_dir.exists():
            return []

        def _read_sqlite_rows(db_path: Path, query: str) -> List[Tuple]:
            tmp_path: Optional[str] = None
            try:
                try:
                    uri = f"file:{db_path}?mode=ro"
                    con = sqlite3.connect(uri, uri=True, timeout=1.0)
                except Exception:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3")
                    tmp_path = tmp.name
                    tmp.close()
                    shutil.copy2(str(db_path), tmp_path)
                    uri = f"file:{tmp_path}?mode=ro"
                    con = sqlite3.connect(uri, uri=True, timeout=1.0)
                try:
                    cur = con.cursor()
                    cur.execute(query)
                    return list(cur.fetchall())
                finally:
                    con.close()
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        def _table_has_column(db_path: Path, table: str, col: str) -> bool:
            try:
                rows = _read_sqlite_rows(db_path, f"PRAGMA table_info({table})")
                return any(str(r[1] or "").lower() == col.lower() for r in rows)
            except Exception:
                return False

        def _chromium_expires_to_unix_seconds(expires_utc: object) -> Optional[int]:
            # Chromium uses microseconds since 1601-01-01 UTC.
            try:
                micros = int(expires_utc)
                if micros <= 0:
                    return None
                return int(micros / 1_000_000 - 11_644_473_600)
            except Exception:
                return None

        def _map_samesite(value: object) -> str:
            # Best-effort mapping across engines (0/1/2/3).
            try:
                v = int(value)
            except Exception:
                return ""
            if v in (0, -1):
                return ""
            if v == 1:
                return "None"
            if v == 2:
                return "Lax"
            if v == 3:
                return "Strict"
            return ""

        candidates = [
            ("firefox", profile_dir / "cookies.sqlite"),
            ("chromium", profile_dir / "Cookies"),
            ("chromium", profile_dir / "Network" / "Cookies"),
            ("chromium", profile_dir / "Default" / "Cookies"),
            ("chromium", profile_dir / "Default" / "Network" / "Cookies"),
        ]
        seen: set[str] = set()
        paths: List[Tuple[str, Path]] = []
        for source, path in candidates:
            p = str(path)
            if p in seen:
                continue
            seen.add(p)
            if path.exists() and path.is_file():
                paths.append((source, path))
        if not paths:
            for path in profile_dir.rglob("cookies.sqlite"):
                p = str(path)
                if p not in seen and path.is_file():
                    paths.append(("firefox", path))
                    seen.add(p)
            for path in profile_dir.rglob("Cookies"):
                p = str(path)
                if p not in seen and path.is_file():
                    paths.append(("chromium", path))
                    seen.add(p)

        out: List[Dict[str, object]] = []
        for source, db_path in paths:
            try:
                if source == "firefox":
                    has_samesite = _table_has_column(db_path, "moz_cookies", "sameSite")
                    if has_samesite:
                        rows = _read_sqlite_rows(
                            db_path,
                            "SELECT host, name, value, path, expiry, isSecure, isHttpOnly, sameSite FROM moz_cookies",
                        )
                    else:
                        rows = _read_sqlite_rows(
                            db_path,
                            "SELECT host, name, value, path, expiry, isSecure, isHttpOnly FROM moz_cookies",
                        )
                    for row in rows:
                        if has_samesite:
                            host, name, value, path, expiry, is_secure, is_http_only, samesite = row
                        else:
                            host, name, value, path, expiry, is_secure, is_http_only = row
                            samesite = None
                        domain = "" if host is None else str(host)
                        cookie_name = "" if name is None else str(name)
                        if not domain or not cookie_name:
                            continue
                        cookie: Dict[str, object] = {
                            "source": source,
                            "domain": domain,
                            "name": cookie_name,
                            "value": "" if value is None else str(value),
                            "path": "/" if not path else str(path),
                            "secure": bool(is_secure),
                            "httpOnly": bool(is_http_only),
                        }
                        try:
                            exp_int = int(expiry) if expiry not in (None, "") else 0
                            if exp_int > 0:
                                cookie["expires"] = exp_int
                        except Exception:
                            pass
                        ss = _map_samesite(samesite)
                        if ss:
                            cookie["sameSite"] = ss
                        out.append(cookie)
                else:
                    has_samesite = _table_has_column(db_path, "cookies", "samesite")
                    if has_samesite:
                        rows = _read_sqlite_rows(
                            db_path,
                            "SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly, samesite FROM cookies",
                        )
                    else:
                        rows = _read_sqlite_rows(
                            db_path,
                            "SELECT host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly FROM cookies",
                        )
                    for row in rows:
                        if has_samesite:
                            host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_http_only, samesite = row
                        else:
                            host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_http_only = row
                            samesite = None
                        domain = "" if host_key is None else str(host_key)
                        cookie_name = "" if name is None else str(name)
                        if not domain or not cookie_name:
                            continue
                        cookie_value = "" if value is None else str(value)
                        if (cookie_value == "" or cookie_value is None) and encrypted_value:
                            cookie_value = "<encrypted>"
                        cookie: Dict[str, object] = {
                            "source": source,
                            "domain": domain,
                            "name": cookie_name,
                            "value": cookie_value,
                            "path": "/" if not path else str(path),
                            "secure": bool(is_secure),
                            "httpOnly": bool(is_http_only),
                        }
                        exp = _chromium_expires_to_unix_seconds(expires_utc)
                        if exp and exp > 0:
                            cookie["expires"] = exp
                        ss = _map_samesite(samesite)
                        if ss:
                            cookie["sameSite"] = ss
                        out.append(cookie)
            except Exception as exc:
                self.logger.debug("Cookie DB read failed (%s): %s", db_path, exc)
                continue

        if out:
            self.logger.debug("Loaded %s cookies from profile DB fallback", len(out))
        return out

    async def _update_timestamp_variable(self) -> None:
        # Local timestamp for filenames/logs: YYYY-MM-DD-HH-MM-SS (no newlines).
        self.variables["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    @staticmethod
    def _normalize_step_payload(step: Dict) -> Dict:
        if not isinstance(step, dict):
            return {}
        if not step.get("value"):
            for legacy_key in ("url", "text", "message"):
                if step.get(legacy_key):
                    step["value"] = step.get(legacy_key)
                    break
        return step

    async def run(self) -> bool:
        steps = self.scenario.steps or []
        scenario_path = self._scenario_path or db_get_scenario_path(self.scenario.name)
        if not (self.debug_session and self.debug_session.enabled):
            ok, _ = await self._execute_steps(steps, self.scenario.name, scenario_path=scenario_path)
            return ok
        return await self._run_debug_loop(scenario_path=scenario_path)

    async def _run_debug_loop(self, *, scenario_path: Optional[Path]) -> bool:
        last_ok: bool = True
        while True:
            steps = self.scenario.steps or []
            ok, reason = await self._execute_steps(steps, self.scenario.name, scenario_path=scenario_path)
            last_ok = bool(ok)

            session = self.debug_session
            if not session or not session.enabled:
                return last_ok
            if session.stop_requested():
                return last_ok

            try:
                session.pause()
            except Exception:
                pass
            try:
                session.notify_finished(last_ok, reason)
            except Exception:
                pass

            # Wait for "Run from step" command; keep browser open and allow hot reload.
            try:
                loop = asyncio.get_running_loop()
                decision = await loop.run_in_executor(None, session.wait_for_command)
            except Exception:
                return last_ok

            if decision.stop or session.stop_requested():
                return last_ok

            # Re-evaluate scenario file so jumps and step list align with latest edits.
            if scenario_path and scenario_path.exists():
                try:
                    payload = json.loads(scenario_path.read_text(encoding="utf-8"))
                    new_steps = payload.get("steps") or []
                    if isinstance(new_steps, list):
                        self.scenario.steps = new_steps
                except Exception:
                    pass

            if decision.jump_to_index is not None:
                try:
                    session.set_initial_step(int(decision.jump_to_index) + 1)
                except Exception:
                    session.set_initial_step(1)
                continue

            if decision.jump_to_tag:
                target = str(decision.jump_to_tag)
                tags = {str(step.get("tag")): idx for idx, step in enumerate(self.scenario.steps or []) if isinstance(step, dict) and step.get("tag")}
                if target in tags:
                    try:
                        session.set_initial_step(int(tags[target]) + 1)
                    except Exception:
                        session.set_initial_step(1)
                else:
                    session.set_initial_step(1)
                continue

    async def _execute_steps(
        self,
        steps: Optional[List[Dict]],
        scenario_name: Optional[str],
        *,
        scenario_path: Optional[Path] = None,
    ) -> Tuple[bool, Optional[str]]:
        steps = steps or []
        tags = {str(step.get("tag")): idx for idx, step in enumerate(steps) if step.get("tag")}
        idx = 0
        label = scenario_name or getattr(self.scenario, "name", "scenario")
        if self.debug_session and self.debug_session.enabled:
            initial = self.debug_session.consume_initial_step()
            if initial is not None and 0 <= int(initial) < len(steps):
                idx = int(initial)
        while idx < len(steps):
            step = steps[idx] or {}
            if self.debug_session and self.debug_session.enabled:
                decision = self.debug_session.before_step(
                    scenario_name=label,
                    account_name=str(getattr(self, "profile_name", "") or ""),
                    step_index=idx,
                    total_steps=len(steps),
                    action=str(step.get("action") or ""),
                    description=str(step.get("description") or step.get("tag") or step.get("label") or step.get("action") or ""),
                    tag=str(step.get("tag") or step.get("label") or ""),
                )
                if decision.stop:
                    return False, "Stopped by debugger"
                if decision.jump_to_index is not None:
                    idx = max(0, int(decision.jump_to_index))
                    continue
                if decision.jump_to_tag:
                    target = str(decision.jump_to_tag)
                    if target in tags:
                        idx = tags[target]
                        continue

            if self.debug_session and self.debug_session.enabled and scenario_path:
                new_steps, new_tags, new_label = self._maybe_hot_reload(steps, tags, label, scenario_path)
                if new_steps is not steps or new_label != label or new_tags is not tags:
                    steps, tags, label = new_steps, new_tags, new_label
                    if idx >= len(steps):
                        idx = max(0, len(steps) - 1)
                    continue
                step = steps[idx] or {}
            outcome = await self._run_step(step, tags, scenario_name=label, step_index=idx)
            if outcome.status == "stop":
                outcome = self._handle_step_error(
                    step,
                    tags,
                    scenario_name=label,
                    step_index=idx,
                    reason=outcome.stop_reason,
                )
            if outcome.status == "end":
                self.logger.info("Scenario %s ended at step %s", label, idx + 1)
                return True, None
            if outcome.status == "jump":
                target = outcome.jump_label or ""
                if target not in tags:
                    msg = f"Jump target {target} not found in scenario {label}"
                    self.logger.error(msg)
                    return False, msg
                idx = tags[target]
                continue
            if outcome.status == "stop":
                reason = outcome.stop_reason or "unknown reason"
                self.logger.error("Scenario %s stopped at step %s: %s", label, idx + 1, reason)
                return False, reason
            next_tag = step.get("next_success_step")
            if next_tag and next_tag in tags:
                idx = tags[next_tag]
                continue
            if step.get("_no_default_links"):
                break
            idx += 1
        return True, None

    def _maybe_hot_reload(
        self,
        steps: List[Dict],
        tags: Dict[str, int],
        label: str,
        scenario_path: Path,
    ) -> Tuple[List[Dict], Dict[str, int], str]:
        try:
            if not scenario_path.exists():
                return steps, tags, label
            mtime = float(scenario_path.stat().st_mtime)
        except Exception:
            return steps, tags, label

        key = str(scenario_path)
        last = self._debug_mtimes.get(key)
        if last is None:
            self._debug_mtimes[key] = mtime
            return steps, tags, label
        if mtime <= last:
            return steps, tags, label

        try:
            payload = json.loads(scenario_path.read_text(encoding="utf-8"))
            new_steps = payload.get("steps") or []
            new_label = str(payload.get("name") or label or scenario_path.stem)
            if not isinstance(new_steps, list):
                return steps, tags, label
        except Exception:
            return steps, tags, label

        self._debug_mtimes[key] = mtime
        if self.debug_session:
            try:
                self.debug_session.notify_reload()
            except Exception:
                pass
        new_tags = {str(step.get("tag")): idx for idx, step in enumerate(new_steps) if isinstance(step, dict) and step.get("tag")}
        return new_steps, new_tags, new_label

    async def _run_step(
        self,
        step: Dict,
        tags: Dict[str, int],
        *,
        scenario_name: Optional[str] = None,
        step_index: Optional[int] = None,
    ) -> StepResult:
        step = self._normalize_step_payload(step or {})
        action = (step.get("action") or "").lower()
        description = step.get("description") or step.get("tag") or action
        self.logger.info("Running step: %s", description)

        try:
            if self._contains_cookies_template(step):
                await self._update_cookies_variable()
            if self._contains_timestamp_template(step):
                await self._update_timestamp_variable()
            if action == "start":
                return StepResult.next()
            if action == "goto":
                return await self._action_goto(step)
            if action == "wait_for_load_state":
                return await self._action_wait_for_load_state(step)
            if action == "wait_element":
                return await self._action_wait_element(step)
            if action == "sleep":
                return await self._action_sleep(step)
            if action == "click":
                return await self._action_click(step)
            if action == "type":
                return await self._action_type(step)
            if action == "set_var":
                return await self._action_set_var(step)
            if action in {"extract_text", "extract"}:
                return await self._action_extract(step)
            if action in {"parse_var", "parse_vars", "parse_variable"}:
                return await self._action_parse_var(step)
            if action in {"compare", "if"}:
                return await self._action_compare(step)
            if action == "new_tab":
                return await self._action_new_tab(step)
            if action == "switch_tab":
                return await self._action_switch_tab(step)
            if action == "close_tab":
                return await self._action_close_tab(step)
            if action == "log":
                return await self._action_log(step)
            if action in {"http_request", "http"}:
                return await self._action_http_request(step)
            if action in {"pop_shared", "pop"}:
                return await self._action_pop_shared(step)
            if action == "run_scenario":
                return await self._action_run_scenario(step)
            if action in {"set_stage", "set_tag"}:
                return await self._action_set_tag(step)
            if action == "write_file":
                return await self._action_write_file(step)
            if action == "end":
                return await self._action_end(step)
            return StepResult.stop(f"Unknown action {action}")
        except Exception as exc:
            return self._handle_step_error(
                step,
                tags,
                scenario_name=scenario_name,
                step_index=step_index,
                exc=exc,
            )

    @staticmethod
    def _escape_pattern_literal(literal: str) -> str:
        if not literal:
            return ""
        parts: List[str] = []
        for chunk in re.split(r"(\s+)", literal):
            if not chunk:
                continue
            if chunk.isspace():
                parts.append(r"\s*")
            else:
                parts.append(re.escape(chunk))
        return "".join(parts)

    @staticmethod
    def _normalize_placeholder_name(name: str) -> str:
        if not name:
            return ""
        parts = str(name).split(":")
        cleaned = parts[-1].strip()
        return cleaned or str(name).strip()

    @classmethod
    def _compile_targets_pattern(cls, template: str):
        placeholder_regex = re.compile(r"{{\s*([^}]+)\s*}}")
        names: List[str] = []
        regex_parts: List[str] = []
        last = 0
        for match in placeholder_regex.finditer(template):
            literal = template[last: match.start()]
            regex_parts.append(cls._escape_pattern_literal(literal))
            regex_parts.append("(.*?)")
            names.append(match.group(1).strip())
            last = match.end()
        regex_parts.append(cls._escape_pattern_literal(template[last:]))
        if not names:
            return [], None
        pattern = "^" + "".join(regex_parts) + "$"
        return names, re.compile(pattern)

    async def _persist_profile_vars(self) -> None:
        """
        Persist current scenario variables to profile-local json for reuse.
        """
        try:
            self._profile_vars_path.parent.mkdir(parents=True, exist_ok=True)
            with self._profile_vars_path.open("w", encoding="utf-8") as fh:
                json.dump(self.variables, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.logger.debug("Failed to persist profile vars to %s: %s", self._profile_vars_path, exc)

    def _persist_shared_setting(self, key: str, raw_value: str) -> None:
        try:
            stored_raw = db_get_setting("shared_variables") or "{}"
            data = json.loads(stored_raw)
        except Exception:
            data = {}
        entry = data.get(key)
        typ = "string"
        if isinstance(entry, dict):
            typ = str(entry.get("type") or "string")
        normalized = raw_value.replace("\r\n", "\n")
        if typ == "list":
            value = [ln.strip() for ln in normalized.split("\n") if ln.strip()]
        else:
            value = normalized
        data[key] = {"type": typ, "value": value}
        try:
            db_set_setting("shared_variables", json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            self.logger.warning("Failed to persist shared var %s: %s", key, exc)

    def _handle_step_error(
        self,
        step: Dict,
        tags: Dict[str, int],
        *,
        scenario_name: Optional[str] = None,
        step_index: Optional[int] = None,
        exc: Optional[Exception] = None,
        reason: Optional[str] = None,
    ) -> StepResult:
        def _format_reason() -> str:
            if reason:
                return str(reason)
            if exc is None:
                return "unknown reason"
            if isinstance(exc, PlaywrightTimeoutError):
                return f"Timeout in action {step.get('action')}: {exc}"
            if isinstance(exc, PlaywrightError):
                return f"Playwright error in {step.get('action')}: {exc}"
            return f"{exc}"

        formatted = _format_reason()
        err_target = step.get("next_error_step")
        if err_target:
            target = str(err_target)
            if target in tags:
                if scenario_name is not None and step_index is not None:
                    self.logger.warning(
                        "Scenario %s error at step %s: %s (jump -> %s)",
                        scenario_name,
                        step_index + 1,
                        formatted,
                        target,
                    )
                else:
                    self.logger.warning("Step error: %s (jump -> %s)", formatted, target)
                return StepResult.jump(target)
            suffix = f" in scenario {scenario_name}" if scenario_name else ""
            return StepResult.stop(f"Error step {target} not found{suffix}")

        return StepResult.stop(formatted)


async def _run_for_account(
    acc: Dict,
    scenario: Scenario,
    shared_vars: Optional[Dict[str, str]],
    *,
    debug_session: Optional[ScenarioDebugSession] = None,
    scenario_path: Optional[Path] = None,
) -> bool:
    logger = logging.getLogger(__name__)
    account_logger = logging.LoggerAdapter(logger, {"profile": str(acc.get("name") or acc.get("email") or "-")})
    proxy = ""
    host = acc.get("proxy_host")
    port = acc.get("proxy_port")
    user = acc.get("proxy_user")
    pwd = acc.get("proxy_password")
    if host and port:
        if user and pwd:
            proxy = f"socks5://{host}:{port}:{user}:{pwd}"
        else:
            proxy = f"socks5://{host}:{port}"
    runner = ScenarioExecutor(
        account_payload=acc,
        proxy=proxy,
        scenario=scenario,
        keep_browser_open=True,
        shared_variables=shared_vars,
        debug_session=debug_session,
        scenario_path=scenario_path,
    )
    if debug_session:
        try:
            runner.add_process_exit_callback(lambda: debug_session.notify_browser_closed_for(str(acc.get("name") or "")))
        except Exception:
            pass
    try:
        await runner.start()
        ok = await runner.run()
        return ok
    except Exception:
        account_logger.exception("Scenario failed for %s", acc["name"])
        return False


def run_scenario(
    accounts: List[Dict],
    scenario: Scenario,
    max_accounts: int,
    shared_vars: Optional[Dict[str, str]] = None,
    *,
    debug_session: Optional[ScenarioDebugSession] = None,
    scenario_path: Optional[Path] = None,
) -> List[Dict]:
    """
    Run provided scenario for up to max_accounts accounts (sequentially).
    Returns list of successfully processed accounts.
    """
    # Debug mode is interactive and keeps the browser open; run a single account.
    to_run = accounts[:1] if debug_session else accounts[:max_accounts]

    async def runner() -> List[Dict]:
        processed: List[Dict] = []
        for acc in to_run:
            if debug_session and debug_session.stop_requested():
                break
            ok = await _run_for_account(
                acc,
                scenario,
                shared_vars,
                debug_session=debug_session,
                scenario_path=scenario_path or db_get_scenario_path(scenario.name),
            )
            if ok:
                processed.append(acc)
        return processed

    return asyncio.run(runner())
