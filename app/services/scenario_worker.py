"""JSON IPC and process supervision for scenarios containing native Python."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import multiprocessing
import os
import signal
import sys
import threading
import time
import uuid
from pathlib import Path

MAX_MESSAGE = 4 * 1024 * 1024


class WorkerCleanupError(RuntimeError):
    """The caller must retain the profile reservation until cleanup is confirmed."""


class Channel:
    def __init__(self, connection):
        self.connection = connection
        self.lock = threading.Lock()

    def send(self, message):
        raw = json.dumps(message, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(raw) > MAX_MESSAGE:
            raise ValueError("Worker message exceeds 4 MiB")
        with self.lock:
            self.connection.send_bytes(raw)

    def receive(self):
        payload = json.loads(self.connection.recv_bytes(MAX_MESSAGE))
        if not isinstance(payload, dict):
            raise ValueError("Invalid worker message")
        return payload


class ProcessTree:
    """Own the entire browser tree; closing the Windows handle kills descendants."""
    def __init__(self, process):
        self.process = process
        self.handle = None
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
                        ("maximum", ctypes.c_size_t), ("active", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]

        class Limits(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", ctypes.c_uint64 * 6),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.kernel = kernel
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, process.sentinel):
            error = ctypes.WinError(ctypes.get_last_error())
            kernel.CloseHandle(handle)
            raise error
        self.handle = handle

    def close(self):
        if self.handle is not None:
            import ctypes
            class Accounting(ctypes.Structure):
                _fields_ = [("times", ctypes.c_int64 * 4), ("faults", ctypes.c_uint32),
                            ("total", ctypes.c_uint32), ("active", ctypes.c_uint32),
                            ("terminated", ctypes.c_uint32)]
            if not self.kernel.TerminateJobObject(self.handle, 1):
                raise WorkerCleanupError("Cannot terminate worker process tree; keep this profile stopped")
            until = time.monotonic() + 5
            while True:
                info = Accounting()
                if not self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
                    raise WorkerCleanupError("Cannot verify browser process cleanup")
                if info.active == 0:
                    break
                if time.monotonic() >= until:
                    raise WorkerCleanupError("Browser processes are still stopping; profile remains reserved")
                time.sleep(0.05)
            if not self.kernel.CloseHandle(self.handle):
                raise WorkerCleanupError("Cannot terminate worker process tree; restart the application after closing the browser")
            self.handle = None
        elif os.name != "nt":
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process.join(5)
        if self.process.is_alive():
            raise WorkerCleanupError("Worker did not exit; profile must remain locked")


def run_worker(account, job, cancel, debug_session=None, tag_updater=None, on_event=None):
    from app.core.shared_vars import SharedVarsManager
    from app.storage import db

    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=True)
    channel = Channel(parent)
    process = context.Process(target=worker_main, args=(child,), name="camouflow-scenario")
    try:
        process.start()
    except Exception:
        parent.close()
        child.close()
        raise
    child.close()
    tree = None
    result = None
    deadline = None
    stopping = None
    error = ""
    artifacts = db.OUTPUTS_DIR / "python-runs" / uuid.uuid4().hex
    artifacts.mkdir(parents=True, exist_ok=False)
    log_size = 0
    debug_threads = []

    def reply(request, value=None, failure=""):
        try:
            channel.send({"type": "reply", "id": request["id"], "value": value, "error": failure})
        except (OSError, EOFError, BrokenPipeError):
            pass

    def debug_reply(message):
        try:
            decision = debug_session.before_step(**message["args"])
            reply(message, dataclasses.asdict(decision))
        except Exception as exc:
            reply(message, failure=str(exc))

    def operation_reply(message):
        try:
            value = _parent_operation(message, account, SharedVarsManager.instance(), tag_updater)
            reply(message, value)
        except Exception as exc:
            reply(message, failure=str(exc))

    try:
        tree = ProcessTree(process)
        channel.send({"type": "start", "account": account, "job": job,
                      "data_root": str(db.DATA_ROOT), "artifacts": str(artifacts),
                      "debug": debug_session is not None})
        startup_deadline = time.monotonic() + 60
        ready = False
        while True:
            now = time.monotonic()
            if debug_session and debug_session.stop_requested():
                cancel.set()
            if (cancel.is_set() or (deadline is not None and now >= deadline) or (not ready and now >= startup_deadline)) and stopping is None:
                error = "Canceled by user" if cancel.is_set() else "Python timeout" if ready else "Worker startup timeout"
                stopping = now
                channel.send({"type": "cancel"})
            if stopping is not None and now - stopping >= 3:
                break
            if parent.poll(0.05):
                try:
                    message = channel.receive()
                except EOFError:
                    break
                kind = message.get("type")
                if kind == "ready":
                    ready = True
                elif kind == "python_start":
                    deadline = now + message["timeout_ms"] / 1000
                    if on_event:
                        on_event(message)
                elif kind == "python_end":
                    deadline = None
                elif kind in {"log", "python_result"}:
                    line = json.dumps(message, ensure_ascii=False) + "\n"
                    if log_size < 2 * 1024 * 1024:
                        with (artifacts / "python.jsonl").open("a", encoding="utf-8") as stream:
                            stream.write(line)
                        log_size += len(line.encode("utf-8"))
                        if on_event:
                            on_event(message)
                elif kind == "request":
                    debug_threads = [t for t in debug_threads if t.is_alive()]
                    if len(debug_threads) >= 8:
                        reply(message, failure="Too many outstanding worker requests")
                        continue
                    if message["method"] == "debug":
                        if debug_session is None:
                            raise ValueError("Unexpected debugger request")
                        thread = threading.Thread(target=debug_reply, args=(message,), daemon=True)
                        debug_threads.append(thread)
                        thread.start()
                    else:
                        thread = threading.Thread(target=operation_reply, args=(message,), daemon=True)
                        debug_threads.append(thread)
                        thread.start()
                elif kind == "result":
                    result = message["value"]
                    break
                else:
                    raise ValueError(f"Unexpected worker event: {kind}")
            elif not process.is_alive():
                break
        if error or result is None:
            if result is None:
                process.join(0.1)
            result = {"status": "canceled" if cancel.is_set() else "failed",
                      "error": error or f"Worker exited unexpectedly ({process.exitcode})"}
        result["artifacts"] = str(artifacts)
        return result
    finally:
        if debug_session:
            debug_session.request_stop()
        if tree is not None:
            tree.close()
        else:
            process.terminate()
            process.join(5)
        parent.close()
        for thread in debug_threads:
            thread.join(1)
        if any(thread.is_alive() for thread in debug_threads):
            raise WorkerCleanupError("A profile operation is still finishing; reservation retained")
        process.close()


def _parent_operation(message, account, manager, tag_updater):
    from app.storage import db
    method, args = message["method"], message.get("args", {})
    if method == "tag" and tag_updater is not None:
        tag_updater(args["value"])
        return None
    with db._STORAGE_LOCK:
        if method == "shared_all":
            return dict(manager.all())
        if method == "shared_get":
            return manager.get(args["key"], args.get("default"))
        if method == "shared_set":
            manager.set(args["key"], args["value"])
            return None
        if method == "shared_pop":
            return manager.pop_first(args["key"])
        if method == "persist_shared":
            from app.services.scenario_engine import ScenarioExecutor
            proxy = type("SharedPersistence", (), {"logger": logging.getLogger(__name__)})()
            ScenarioExecutor._persist_shared_setting(proxy, args["key"], str(manager.get(args["key"], "")))
            return None
        if method == "account_update":
            if tag_updater is not None:
                raise ValueError("Updating cloud account fields from this step is unsupported")
            db.db_update_account(account["name"], args["updates"])
            return None
        if method == "tag":
            db.db_update_stage(account["name"], args["value"])
            return None
    raise ValueError(f"Unsupported worker request: {method}")


def worker_main(connection):
    if os.name != "nt":
        os.setsid()
    channel = Channel(connection)
    payload = channel.receive()
    os.environ["CAMOUFLOW_DATA_DIR"] = payload["data_root"]
    os.chdir(payload["artifacts"])
    cancel = threading.Event()
    pending = {}
    pending_lock = threading.Lock()

    def request(method, args=None):
        identifier = uuid.uuid4().hex
        event = threading.Event()
        holder = {}
        with pending_lock:
            pending[identifier] = (event, holder)
        try:
            channel.send({"type": "request", "id": identifier, "method": method, "args": args or {}})
            while not event.wait(0.05):
                if cancel.is_set():
                    raise RuntimeError("Canceled by user")
            if holder.get("error"):
                raise RuntimeError(holder["error"])
            return holder.get("value")
        finally:
            with pending_lock:
                pending.pop(identifier, None)

    def listen():
        try:
            while True:
                message = channel.receive()
                if message.get("type") == "cancel":
                    cancel.set()
                elif message.get("type") == "reply":
                    with pending_lock:
                        target = pending.get(message["id"])
                        if target:
                            target[1].update(message)
                            target[0].set()
        except (EOFError, OSError, ValueError):
            cancel.set()

    threading.Thread(target=listen, daemon=True).start()

    class LogOutput:
        def __init__(self):
            self.size = 0
            self.messages = 0

        def write(self, value):
            value = str(value)
            if value.strip() and self.size < 1024 * 1024 and self.messages < 2000:
                channel.send({"type": "log", "text": value[:8192]})
                self.size += len(value.encode("utf-8"))
                self.messages += 1
                if self.messages == 2000 or self.size >= 1024 * 1024:
                    channel.send({"type": "log", "text": "Python log limit reached; further output is suppressed."})
            return len(value)

        def flush(self):
            pass

    output = LogOutput()
    sys.stdout = sys.stderr = output
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(output)], force=True)
    from app.services.scenario_debug import ScenarioDebugDecision, ScenarioDebugSession
    from app.services.scenario_engine import ScenarioExecutor
    from app.services.proxy_policy import account_proxy
    from app.storage.db import Scenario

    class DebugProxy(ScenarioDebugSession):
        def before_step(self, **kwargs):
            return ScenarioDebugDecision(**request("debug", kwargs))

    class SharedProxy:
        def all(self):
            return request("shared_all")

        def get(self, key, default=None):
            return request("shared_get", {"key": key, "default": default})

        def set(self, key, value):
            return request("shared_set", {"key": key, "value": value})

        def pop_first(self, key):
            return request("shared_pop", {"key": key})

    async def execute():
        account, job = payload["account"], payload["job"]
        engine = account.get("_browser_engine") or account.get("browser_engine") or "camoufox"
        account["_browser_engine"] = engine
        account["_browser_settings"] = account.get("cloakbrowser_settings" if engine == "cloakbrowser" else "camoufox_settings", {})
        scenario = Scenario(job["scenario"], job["steps"], job.get("description", ""))
        runner = ScenarioExecutor(account, account_proxy(account), scenario, keep_browser_open=False,
                                  cancel_event=cancel, debug_session=DebugProxy(cancel_event=cancel) if payload["debug"] else None)
        runner._python_worker = True
        runner.add_process_exit_callback(cancel.set)
        runner._worker_emit = channel.send
        runner.shared_manager = SharedProxy()
        runner.shared_vars = runner.shared_manager.all()
        runner._scenario_library = {name: Scenario(name, row["steps"], row.get("description", "")) for name, row in job.get("library", {}).items()}
        runner._maybe_hot_reload = lambda steps, tags, label, path: (steps, tags, label)
        runner._tag_updater = lambda value: request("tag", {"value": value})
        runner._account_updater = lambda updates: request("account_update", {"updates": updates})
        runner._persist_shared_setting = lambda key, value: request("persist_shared", {"key": key, "value": value})
        task = asyncio.current_task()

        async def watch_cancel():
            while not cancel.is_set():
                await asyncio.sleep(0.05)
            task.cancel()

        watcher = asyncio.create_task(watch_cancel())
        channel.send({"type": "ready"})
        try:
            await runner.start()
            runner._run_artifact_dir = Path(payload["artifacts"])
            await runner.start_run_capture()
            ok, reason = await runner._execute_steps(scenario.steps, scenario.name)
            return {"status": "success" if ok else "failed", "error": reason or ""}
        except asyncio.CancelledError:
            return {"status": "canceled", "error": "Canceled by user"}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}
        finally:
            watcher.cancel()
            try:
                await runner.stop_run_capture()
            finally:
                await runner.close(force=True)

    try:
        channel.send({"type": "result", "value": asyncio.run(execute())})
    except BaseException as exc:
        channel.send({"type": "result", "value": {"status": "failed", "error": str(exc)}})
    finally:
        connection.close()
